import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import jwt


class OidcError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        super().__init__(message)


def _https_url(value, name, loopback_http=False):
    parsed = urllib.parse.urlsplit(value)
    allowed_http = loopback_http and parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if not parsed.netloc or parsed.fragment or parsed.username or parsed.password or (parsed.scheme != 'https' and not allowed_http):
        raise ValueError(f'{name} harus berupa URL HTTPS' + (' atau HTTP loopback' if loopback_http else '') + '.')
    return value


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    label: str = 'SSO perusahaan'

    def __post_init__(self):
        issuer = self.issuer.strip().rstrip('/')
        redirect_uri = self.redirect_uri.strip()
        label = self.label.strip()
        _https_url(issuer, 'Issuer OIDC')
        _https_url(redirect_uri, 'Redirect URI OIDC', loopback_http=True)
        if not 1 <= len(self.client_id) <= 500 or not self.client_id.strip():
            raise ValueError('Client ID OIDC wajib diisi.')
        if not 1 <= len(self.client_secret) <= 2000 or not self.client_secret.strip():
            raise ValueError('Client secret OIDC wajib diisi.')
        if not 1 <= len(label) <= 80:
            raise ValueError('Label OIDC harus 1 sampai 80 karakter.')
        object.__setattr__(self, 'issuer', issuer)
        object.__setattr__(self, 'redirect_uri', redirect_uri)
        object.__setattr__(self, 'client_id', self.client_id.strip())
        object.__setattr__(self, 'label', label)

    @classmethod
    def from_env(cls):
        names = ('BEELOFT_OIDC_ISSUER', 'BEELOFT_OIDC_CLIENT_ID', 'BEELOFT_OIDC_CLIENT_SECRET',
                 'BEELOFT_OIDC_REDIRECT_URI')
        values = {name: os.environ.get(name, '') for name in names}
        if not any(values.values()):
            return None
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError('Konfigurasi OIDC belum lengkap: ' + ', '.join(missing))
        return cls(values[names[0]], values[names[1]], values[names[2]], values[names[3]],
                   os.environ.get('BEELOFT_OIDC_LABEL', 'SSO perusahaan'))


class UrlTransport:
    @staticmethod
    def _read(request, http_error_status=503):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                content = response.read(1_000_001)
        except urllib.error.HTTPError as exc:
            message = 'Penyedia identitas menolak pertukaran code.' if http_error_status == 401 else 'Penyedia identitas belum dapat dihubungi.'
            raise OidcError(http_error_status, message) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OidcError(503, 'Penyedia identitas belum dapat dihubungi.') from exc
        if len(content) > 1_000_000:
            raise OidcError(503, 'Respons penyedia identitas terlalu besar.')
        try:
            return json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OidcError(503, 'Respons penyedia identitas tidak valid.') from exc

    def json_get(self, url):
        return self._read(urllib.request.Request(url, headers={'Accept': 'application/json'}))

    def form_post(self, url, data, basic_auth=None):
        body = urllib.parse.urlencode(data).encode()
        headers={'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
        if basic_auth:
            encoded=base64.b64encode(f'{basic_auth[0]}:{basic_auth[1]}'.encode()).decode()
            headers['Authorization']='Basic '+encoded
        return self._read(urllib.request.Request(url, data=body, headers=headers),http_error_status=401)


class OidcClient:
    SAFE_ALGORITHMS = ('RS256', 'ES256')

    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport or UrlTransport()
        self._metadata = None

    def metadata(self):
        if self._metadata is not None:
            return self._metadata
        url = self.config.issuer + '/.well-known/openid-configuration'
        data = self.transport.json_get(url)
        if not isinstance(data, dict) or data.get('issuer') != self.config.issuer:
            raise OidcError(503, 'Issuer pada discovery OIDC tidak cocok.')
        for name in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
            value = data.get(name, '')
            try:
                _https_url(value, name)
            except ValueError as exc:
                raise OidcError(503, 'Metadata penyedia identitas tidak aman.') from exc
        methods = data.get('token_endpoint_auth_methods_supported', ['client_secret_basic'])
        if not any(value in methods for value in ('client_secret_post','client_secret_basic')):
            raise OidcError(503, 'Metode autentikasi token endpoint tidak didukung.')
        algorithms = data.get('id_token_signing_alg_values_supported', [])
        if not any(value in self.SAFE_ALGORITHMS for value in algorithms):
            raise OidcError(503, 'Algoritma tanda tangan ID token tidak didukung.')
        self._metadata = data
        return data

    def authorization_request(self):
        metadata = self.metadata()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        query = urllib.parse.urlencode({
            'response_type': 'code', 'client_id': self.config.client_id,
            'redirect_uri': self.config.redirect_uri, 'scope': 'openid profile email',
            'state': state, 'nonce': nonce, 'code_challenge': challenge,
            'code_challenge_method': 'S256'})
        return metadata['authorization_endpoint'] + '?' + query, state, nonce, verifier

    def exchange(self, code, verifier, nonce_hash):
        metadata = self.metadata()
        methods=metadata.get('token_endpoint_auth_methods_supported',['client_secret_basic'])
        use_post='client_secret_post' in methods
        data={
            'grant_type': 'authorization_code', 'code': code,
            'redirect_uri': self.config.redirect_uri, 'client_id': self.config.client_id,
            'code_verifier': verifier}
        if use_post:
            data['client_secret']=self.config.client_secret
        token_response = self.transport.form_post(metadata['token_endpoint'],data,
            None if use_post else (self.config.client_id,self.config.client_secret))
        token = token_response.get('id_token') if isinstance(token_response, dict) else None
        if not isinstance(token, str) or len(token) > 20_000:
            raise OidcError(401, 'Penyedia identitas tidak mengembalikan ID token yang valid.')
        jwks = self.transport.json_get(metadata['jwks_uri'])
        keys = jwks.get('keys') if isinstance(jwks, dict) else None
        if not isinstance(keys, list):
            raise OidcError(503, 'JWKS penyedia identitas tidak valid.')
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get('alg')
            supported = metadata.get('id_token_signing_alg_values_supported', [])
            if algorithm not in self.SAFE_ALGORITHMS or algorithm not in supported:
                raise OidcError(401, 'Algoritma ID token tidak diizinkan.')
            candidates = [key for key in keys if key.get('kid') == header.get('kid')
                          and key.get('use','sig') == 'sig']
            if not candidates and header.get('kid') is None and len(keys) == 1:
                candidates = keys
            if len(candidates) != 1:
                raise OidcError(401, 'Kunci tanda tangan ID token tidak ditemukan.')
            key = jwt.PyJWK.from_dict(candidates[0], algorithm=algorithm).key
            claims = jwt.decode(token, key, algorithms=[algorithm], audience=self.config.client_id,
                                issuer=self.config.issuer, leeway=60,
                                options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'nonce']})
        except OidcError:
            raise
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise OidcError(401, 'ID token tidak lolos verifikasi.') from exc
        supplied_nonce = hashlib.sha256(str(claims['nonce']).encode()).hexdigest()
        if not secrets.compare_digest(supplied_nonce, nonce_hash):
            raise OidcError(401, 'Nonce login OIDC tidak cocok.')
        audience = claims['aud']
        if claims.get('azp') is not None and claims['azp'] != self.config.client_id:
            raise OidcError(401, 'Authorized party ID token tidak cocok.')
        if isinstance(audience, list) and len(audience) > 1 and 'azp' not in claims:
            raise OidcError(401, 'Authorized party ID token tidak cocok.')
        # Subject adalah identifier milik penyedia: nilainya dipakai apa adanya dan tidak pernah
        # dipangkas. Subject dengan spasi awal/akhir ditolak karena pemangkasan menyatukan dua
        # subject berbeda ke satu identitas, dan nilai seperti itu memang tidak dapat disimpan
        # persis oleh constraint oidc_identities.
        subject = claims['sub']
        if (not isinstance(subject, str) or subject != subject.strip()
                or not 1 <= len(subject) <= 500):
            raise OidcError(401, 'Subject ID token tidak valid.')
        return {'issuer': self.config.issuer, 'subject': subject}
