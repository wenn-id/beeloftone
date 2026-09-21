import base64
import hashlib
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, quote, unquote_plus, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.oidc import OidcClient, OidcConfig, UrlTransport
from beeloft.store import DomainError, Store


def encoded_integer(value):
    raw=value.to_bytes((value.bit_length()+7)//8,'big')
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


class FakeOidcTransport:
    def __init__(self, issuer, authorization_endpoint=None):
        self.issuer=issuer
        self.private_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        numbers=self.private_key.public_key().public_numbers()
        self.jwks={'keys':[{'kty':'RSA','kid':'test-key','use':'sig','alg':'RS256',
                            'n':encoded_integer(numbers.n),'e':encoded_integer(numbers.e)}]}
        self.discovery={'issuer':issuer,'authorization_endpoint':authorization_endpoint or issuer+'/authorize',
            'token_endpoint':issuer+'/token','jwks_uri':issuer+'/jwks',
            'token_endpoint_auth_methods_supported':['client_secret_post'],
            'id_token_signing_alg_values_supported':['RS256']}
        self.id_token=None
        self.token_requests=[]

    def json_get(self,url):
        if url.endswith('/.well-known/openid-configuration'):
            return self.discovery
        if url==self.discovery['jwks_uri']:
            return self.jwks
        raise AssertionError(url)

    def form_post(self,url,data,basic_auth=None):
        self.token_requests.append((url,data,basic_auth))
        return {'id_token':self.id_token}

    def token(self,nonce,subject='employee-123',audience='beeloft-client',**changes):
        moment=datetime.now(timezone.utc)
        claims={'iss':self.issuer,'sub':subject,'aud':audience,'nonce':nonce,
                'iat':moment,'exp':moment+timedelta(minutes=5)}|changes
        return jwt.encode(claims,self.private_key,algorithm='RS256',headers={'kid':'test-key'})


def decoded_basic_credentials(header):
    """Membaca header Basic seperti provider menurut RFC 6749 §2.3.1: pisahkan pada titik dua
    pertama, lalu form-decode username dan password secara terpisah."""
    scheme,_,payload=header.partition(' ')
    assert scheme=='Basic',header
    client_id,_,client_secret=base64.b64decode(payload).decode().partition(':')
    return unquote_plus(client_id),unquote_plus(client_secret)


class ProviderUrlTransport(UrlTransport):
    """UrlTransport dengan jaringan dimatikan: request yang benar-benar dibangun form_post
    disimpan supaya dapat dibaca persis seperti provider membacanya."""

    def __init__(self,issuer,methods):
        self.private_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        numbers=self.private_key.public_key().public_numbers()
        self.jwks={'keys':[{'kty':'RSA','kid':'test-key','use':'sig','alg':'RS256',
                            'n':encoded_integer(numbers.n),'e':encoded_integer(numbers.e)}]}
        self.discovery={'issuer':issuer,'authorization_endpoint':issuer+'/authorize',
            'token_endpoint':issuer+'/token','jwks_uri':issuer+'/jwks',
            'token_endpoint_auth_methods_supported':methods,
            'id_token_signing_alg_values_supported':['RS256']}
        self.id_token=None
        self.token_requests=[]

    def _read(self,request,http_error_status=503):
        url=request.full_url
        if url.endswith('/.well-known/openid-configuration'):
            return self.discovery
        if url==self.discovery['token_endpoint']:
            self.token_requests.append(request)
            return {'id_token':self.id_token}
        if url==self.discovery['jwks_uri']:
            return self.jwks
        raise AssertionError(url)

    def token(self,nonce,audience):
        moment=datetime.now(timezone.utc)
        claims={'iss':self.discovery['issuer'],'sub':'employee-123','aud':audience,'nonce':nonce,
                'iat':moment,'exp':moment+timedelta(minutes=5)}
        return jwt.encode(claims,self.private_key,algorithm='RS256',headers={'kid':'test-key'})


class OidcSsoTest(TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'test.sqlite3'
        self.config=OidcConfig('https://identity.example','beeloft-client','client-secret',
                               'http://127.0.0.1:8000/api/sso/callback','Identitas Beeloft')
        self.transport=FakeOidcTransport(self.config.issuer)
        self.app=create_app(self.path,self.config,self.transport)
        self.client=TestClient(self.app).__enter__();self.addCleanup(self.client.__exit__,None,None,None)
        self.admin=self.app.state.store.provision_user('Pemilik','admin')

    def begin(self):
        response=self.client.get('/api/sso/login',follow_redirects=False)
        self.assertEqual(response.status_code,302,response.text)
        query=parse_qs(urlsplit(response.headers['location']).query)
        return response,query

    def callback(self,query,code='authorization-code'):
        return self.client.get('/api/sso/callback',params={'code':code,'state':query['state'][0]},
                               follow_redirects=False)

    def endpoint_client(self,endpoint):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'endpoint.sqlite3'
        transport=FakeOidcTransport(self.config.issuer,endpoint)
        app=create_app(path,self.config,transport)
        client=TestClient(app).__enter__();self.addCleanup(client.__exit__,None,None,None)
        return client,transport,app,path

    def test_authorization_code_pkce_login_creates_browser_session(self):
        self.app.state.store.link_oidc_identity(self.config.issuer,'employee-123',self.admin['id'])
        self.assertEqual(self.client.get('/api/sso').json(),{
            'enabled':True,'label':'Identitas Beeloft','login_url':'/api/sso/login'})
        response,query=self.begin()
        self.assertEqual(urlsplit(response.headers['location']).path,'/authorize')
        self.assertEqual(query['response_type'],['code']);self.assertEqual(query['scope'],['openid profile email'])
        self.assertEqual(query['code_challenge_method'],['S256']);self.assertEqual(query['client_id'],['beeloft-client'])
        self.assertNotIn('client_secret',query)
        state_cookie=next(value for value in response.headers.get_list('set-cookie')
                          if value.startswith('beeloft_oidc_state='))
        self.assertIn('HttpOnly',state_cookie);self.assertIn('SameSite=lax',state_cookie)
        self.assertIn('Path=/api/sso/callback',state_cookie)
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute('SELECT state_hash,nonce_hash,code_verifier FROM oidc_login_attempts').fetchone()
            self.assertEqual(row[0],hashlib.sha256(query['state'][0].encode()).hexdigest())
            self.assertEqual(row[1],hashlib.sha256(query['nonce'][0].encode()).hexdigest())
            self.assertNotIn(query['state'][0],row);self.assertNotIn(query['nonce'][0],row)
        self.transport.id_token=self.transport.token(query['nonce'][0])
        callback=self.callback(query)
        self.assertEqual(callback.status_code,303,callback.text);self.assertEqual(callback.headers['location'],'/')
        cookies=callback.headers.get_list('set-cookie')
        self.assertTrue(any(value.startswith('beeloft_session=') and 'HttpOnly' in value for value in cookies))
        self.assertTrue(any(value.startswith('beeloft_csrf=') and 'HttpOnly' not in value for value in cookies))
        self.assertEqual(self.client.get('/api/me').json()['id'],self.admin['id'])
        request=self.transport.token_requests[0][1]
        self.assertEqual(request['code'],'authorization-code');self.assertEqual(request['client_secret'],'client-secret')
        self.assertEqual(request['code_verifier'],row[2])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM oidc_login_attempts').fetchone()[0],0)
            self.assertIsNotNone(db.execute('SELECT last_login_at FROM oidc_identities').fetchone()[0])

    def test_authorization_endpoint_query_is_kept_as_separate_parameters(self):
        oauth=('response_type','client_id','redirect_uri','scope','state','nonce','code_challenge',
               'code_challenge_method')
        for suffix,preserved in (
                ('/authorize',{}),
                ('/authorize?',{}),
                ('/authorize?p=tenant-policy',{'p':['tenant-policy']}),
                ('/authorize?p=tenant-policy&realm=beeloft',{'p':['tenant-policy'],'realm':['beeloft']})):
            with self.subTest(endpoint=suffix):
                client,transport,app,path=self.endpoint_client(self.config.issuer+suffix)
                admin=app.state.store.provision_user('Pemilik','admin')
                app.state.store.link_oidc_identity(self.config.issuer,'employee-123',admin['id'])
                response=client.get('/api/sso/login',follow_redirects=False)
                self.assertEqual(response.status_code,302,response.text)
                location=urlsplit(response.headers['location'])
                self.assertEqual(location.path,'/authorize')
                query=parse_qs(location.query)
                self.assertEqual(set(query),set(preserved)|set(oauth))
                for name in preserved:
                    self.assertEqual(query[name],preserved[name])
                self.assertEqual(query['response_type'],['code'])
                self.assertEqual(query['client_id'],['beeloft-client'])
                self.assertEqual(query['redirect_uri'],[self.config.redirect_uri])
                self.assertEqual(query['scope'],['openid profile email'])
                self.assertEqual(query['code_challenge_method'],['S256'])
                with closing(sqlite3.connect(path)) as db:
                    verifier=db.execute('SELECT code_verifier FROM oidc_login_attempts').fetchone()[0]
                challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
                self.assertEqual(query['code_challenge'],[challenge])
                transport.id_token=transport.token(query['nonce'][0])
                callback=client.get('/api/sso/callback',follow_redirects=False,
                                    params={'code':'authorization-code','state':query['state'][0]})
                self.assertEqual(callback.status_code,303,callback.text)
                self.assertEqual(client.get('/api/me').json()['id'],admin['id'])

    def lenient_client(self):
        """Client yang menerjemahkan exception yang tidak tertangani menjadi respons 500.

        Tanpa ini, handler yang melempar menggagalkan test dengan exception aslinya, sehingga test
        tidak dapat membedakan penolakan 4xx yang benar dari kegagalan server.
        """
        return TestClient(self.app,raise_server_exceptions=False)

    def test_state_outside_the_issued_alphabet_is_rejected_without_a_server_error(self):
        """Issue #35: `/api/sso/callback?code=x&state=%C3%A9` dijawab 401, bukan 500."""
        self.app.state.store.link_oidc_identity(self.config.issuer,'employee-123',self.admin['id'])
        client=self.lenient_client()
        login=client.get('/api/sso/login',follow_redirects=False)
        self.assertEqual(login.status_code,302,login.text)
        query=parse_qs(urlsplit(login.headers['location']).query)
        for state in ('%C3%A9','%C3%A9%C3%A9','%E2%82%AC','%00','abc%20def','a.b','a%2Bb',
                      quote(query['state'][0])+'%C3%A9'):
            with self.subTest(state=state):
                response=client.get(f'/api/sso/callback?code=authorization-code&state={state}',
                                    follow_redirects=False)
                self.assertEqual(response.status_code,401,response.text)
                self.assertEqual(response.json()['detail'],'State login OIDC tidak cocok dengan browser.')
                self.assertFalse(client.cookies.get('beeloft_session'))
        # State tidak sah tidak boleh menukar code maupun menghabiskan attempt yang tersimpan.
        self.assertEqual(len(self.transport.token_requests),0)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM oidc_login_attempts').fetchone()[0],1)
        self.transport.id_token=self.transport.token(query['nonce'][0])
        callback=client.get('/api/sso/callback',follow_redirects=False,
                            params={'code':'authorization-code','state':query['state'][0]})
        self.assertEqual(callback.status_code,303,callback.text)
        self.assertEqual(client.get('/api/me').json()['id'],self.admin['id'])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM oidc_login_attempts').fetchone()[0],0)
        replay=client.get('/api/sso/callback',follow_redirects=False,
                          params={'code':'authorization-code','state':query['state'][0]})
        self.assertEqual(replay.status_code,401,replay.text)
        self.assertEqual(len(self.transport.token_requests),1)

    def test_non_ascii_state_cookie_is_rejected_without_a_server_error(self):
        """Cookie state juga dikendalikan pengirim: byte non-ASCII di dalamnya tidak boleh 500."""
        client=self.lenient_client()
        login=client.get('/api/sso/login',follow_redirects=False)
        self.assertEqual(login.status_code,302,login.text)
        state=parse_qs(urlsplit(login.headers['location']).query)['state'][0]
        client.cookies.clear()
        for cookie in (b'beeloft_oidc_state=\xe9',b'beeloft_oidc_state=\xe9\xe9',
                       b'beeloft_oidc_state='+state.encode()+b'\xe9'):
            with self.subTest(cookie=cookie):
                response=client.get('/api/sso/callback',follow_redirects=False,
                                    params={'code':'authorization-code','state':state},
                                    headers={'Cookie':cookie})
                self.assertEqual(response.status_code,401,response.text)
                self.assertFalse(client.cookies.get('beeloft_session'))
        self.assertEqual(len(self.transport.token_requests),0)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM oidc_login_attempts').fetchone()[0],1)

    def test_nonce_and_state_are_one_time_and_unknown_identity_is_denied(self):
        _,query=self.begin()
        other=TestClient(self.app)
        self.assertEqual(other.get('/api/sso/callback',params={
            'code':'authorization-code','state':query['state'][0]}).status_code,401)
        self.assertEqual(len(self.transport.token_requests),0)
        self.transport.id_token=self.transport.token('wrong-nonce')
        self.assertEqual(self.callback(query).status_code,401)
        self.assertEqual(self.callback(query).status_code,401)
        self.assertEqual(len(self.transport.token_requests),1)
        _,query=self.begin();self.transport.id_token=self.transport.token(query['nonce'][0])
        self.assertEqual(self.callback(query).status_code,403)
        self.assertFalse(self.client.cookies.get('beeloft_session'))

    def test_disabled_user_and_invalid_token_claims_are_denied(self):
        self.app.state.store.link_oidc_identity(self.config.issuer,'employee-123',self.admin['id'])
        _,query=self.begin();self.transport.id_token=self.transport.token(query['nonce'][0],audience='other-client')
        self.assertEqual(self.callback(query).status_code,401)
        past=datetime.now(timezone.utc)-timedelta(minutes=10)
        _,query=self.begin();self.transport.id_token=self.transport.token(
            query['nonce'][0],iat=past,exp=past+timedelta(minutes=1))
        self.assertEqual(self.callback(query).status_code,401)
        self.app.state.store.disable_user(self.admin['id'])
        _,query=self.begin();self.transport.id_token=self.transport.token(query['nonce'][0])
        self.assertEqual(self.callback(query).status_code,401)

    def test_disabled_configuration_and_environment_validation(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{},clear=True):
            client=TestClient(create_app(Path(folder)/'disabled.sqlite3'))
            self.assertEqual(client.get('/api/sso').json(),{'enabled':False,'label':'','login_url':''})
            self.assertEqual(client.get('/api/sso/login').status_code,404)
            self.assertEqual(client.get('/api/sso/callback').status_code,404)
        with patch.dict(os.environ,{'BEELOFT_OIDC_ISSUER':'https://identity.example'},clear=True):
            with self.assertRaises(RuntimeError):
                OidcConfig.from_env()
        with self.assertRaises(ValueError):
            OidcConfig('http://identity.example','id','secret','http://127.0.0.1/callback')

    def test_identity_mapping_backup_and_migration_from_43(self):
        linked=self.app.state.store.link_oidc_identity(self.config.issuer+'/','employee-123',self.admin['id'])
        self.assertEqual((linked['issuer'],linked['subject']),(self.config.issuer,'employee-123'))
        with self.assertRaises(DomainError) as duplicate:
            self.app.state.store.link_oidc_identity(self.config.issuer,'employee-456',self.admin['id'])
        self.assertEqual(duplicate.exception.status,409)
        with self.assertRaises(DomainError):
            self.app.state.store.link_oidc_identity('http://unsafe','x',self.admin['id'])
        backup=self.path.with_name('oidc-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).authenticate_oidc_identity(self.config.issuer,'employee-123')['id'],self.admin['id'])
        self.app.state.store.unlink_oidc_identity(self.config.issuer,'employee-123')
        with self.assertRaises(DomainError):
            self.app.state.store.unlink_oidc_identity(self.config.issuer,'employee-123')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE oidc_login_attempts');db.execute('DROP TABLE oidc_identities')
            db.execute('PRAGMA user_version=43');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],55)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM oidc_identities').fetchone()[0],0)

    def test_identity_values_are_stored_and_compared_exactly(self):
        store=self.app.state.store
        store.link_oidc_identity(self.config.issuer,'employee-123',self.admin['id'])
        for subject in (' employee-123','employee-123 ',' employee-123 ',123):
            with self.assertRaises(DomainError) as linked:
                store.link_oidc_identity(self.config.issuer,subject,self.admin['id'])
            self.assertEqual(linked.exception.status,422)
            with self.assertRaises(DomainError) as unlinked:
                store.unlink_oidc_identity(self.config.issuer,subject)
            self.assertEqual(unlinked.exception.status,422)
            with self.assertRaises(DomainError) as looked_up:
                store.authenticate_oidc_identity(self.config.issuer,subject)
            self.assertEqual(looked_up.exception.status,422)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT issuer,subject FROM oidc_identities').fetchall(),
                             [(self.config.issuer,'employee-123')])
        self.assertEqual(store.authenticate_oidc_identity(self.config.issuer,'employee-123')['id'],
                         self.admin['id'])

    def test_signed_token_with_distinct_whitespace_subject_does_not_open_the_linked_account(self):
        self.app.state.store.link_oidc_identity(self.config.issuer,'employee-123',self.admin['id'])
        for subject in (' employee-123 ','employee-123 '):
            _,query=self.begin()
            self.transport.id_token=self.transport.token(query['nonce'][0],subject=subject)
            response=self.callback(query)
            self.assertEqual(response.status_code,401,response.text)
            self.assertFalse(self.client.cookies.get('beeloft_session'))
            self.assertEqual(self.client.get('/api/me').status_code,401)
        _,query=self.begin();self.transport.id_token=self.transport.token(query['nonce'][0])
        self.assertEqual(self.callback(query).status_code,303)
        self.assertEqual(self.client.get('/api/me').json()['id'],self.admin['id'])


class OidcBasicAuthTest(TestCase):
    """Kredensial client_secret_basic diuji lewat header yang dibangun UrlTransport sendiri."""

    def exchange(self,client_id,client_secret,methods):
        config=OidcConfig('https://identity.example',client_id,client_secret,
                          'http://127.0.0.1:8000/api/sso/callback')
        transport=ProviderUrlTransport(config.issuer,methods)
        client=OidcClient(config,transport)
        nonce='nonce-'+client_id
        transport.id_token=transport.token(nonce,config.client_id)
        identity=client.exchange('authorization-code','code-verifier',
                                 hashlib.sha256(nonce.encode()).hexdigest())
        return config,transport,identity

    def test_basic_auth_form_encodes_each_credential_before_base64(self):
        cases=(('client:id','secret+percent%value'),('client id','secret value'),
               ('100%client','a%2Bb'),('client:with:colon','secret:with:colon'))
        for client_id,client_secret in cases:
            with self.subTest(client_id=client_id,client_secret=client_secret):
                config,transport,identity=self.exchange(client_id,client_secret,['client_secret_basic'])
                self.assertEqual(identity,{'issuer':config.issuer,'subject':'employee-123'})
                request=transport.token_requests[0]
                self.assertEqual(decoded_basic_credentials(request.headers['Authorization']),
                                 (config.client_id,config.client_secret))
                form=parse_qs(request.data.decode())
                self.assertNotIn('client_secret',form)
                self.assertEqual(form['client_id'],[config.client_id])

    def test_client_secret_post_keeps_the_secret_in_the_form_body(self):
        cases=(('beeloft-client','secret+percent%value'),('client id','secret value'),
               ('100%client','a%2Bb'))
        for client_id,client_secret in cases:
            with self.subTest(client_id=client_id,client_secret=client_secret):
                config,transport,identity=self.exchange(client_id,client_secret,['client_secret_post'])
                self.assertEqual(identity,{'issuer':config.issuer,'subject':'employee-123'})
                request=transport.token_requests[0]
                self.assertIsNone(request.headers.get('Authorization'))
                form=parse_qs(request.data.decode())
                self.assertEqual(form['client_secret'],[config.client_secret])
                self.assertEqual(form['client_id'],[config.client_id])
