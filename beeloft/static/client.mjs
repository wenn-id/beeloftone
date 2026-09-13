export function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[character]));
}

export function formatMaterialQuantity(quantity, unit) {
  const text = String(quantity), [whole,fraction=''] = text.replace(/^-/, '').split('.');
  const decimal = fraction.replace(/0+$/, '');
  return `${text.startsWith('-') ? '-' : ''}${new Intl.NumberFormat('id-ID').format(BigInt(whole))}${decimal ? ','+decimal : ''} ${unit}`;
}

export function displayDate(value) {
  return new Intl.DateTimeFormat('id-ID', {day:'numeric', month:'short', year:'numeric', timeZone:'Asia/Jakarta'}).format(new Date(value.length === 10 ? value + 'T12:00:00+07:00' : value));
}

export class Api {
  constructor(fetcher = (...args) => fetch(...args)) { this.fetcher = fetcher; this.key = ''; this.csrf = ''; }
  transaction(path, body) { return {path, body: JSON.stringify(body), key: crypto.randomUUID()}; }
  get(path) { return this.request(path); }
  post(path, body) { return this.request(path, {body:JSON.stringify(body), readOnly:true}); }
  download(path) { return this.request(path, null, true); }
  save(transaction) { return this.request(transaction.path, transaction); }
  async request(path, transaction, download = false) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const headers = {};
      if (this.key) headers['X-API-Key'] = this.key;
      if (transaction) {
        headers['Content-Type'] = 'application/json';
        if (transaction.key) headers['Idempotency-Key'] = transaction.key;
        if (!this.key) {
          const cookie = typeof document === 'undefined' ? '' : document.cookie.split('; ').find(row => row.startsWith('beeloft_csrf='))?.slice(13);
          const csrf = this.csrf || (cookie ? decodeURIComponent(cookie) : '');
          if (csrf) headers['X-CSRF-Token'] = csrf;
        }
      }
      const response = await this.fetcher(path, {method:transaction ? 'POST' : 'GET', headers,
        body:transaction?.body, signal:controller.signal, cache:'no-store', credentials:'same-origin'});
      const data = response.ok && download ? await response.blob() : await response.json();
      if (!response.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join('; ') : data.detail;
        throw Object.assign(new Error(detail || 'Permintaan gagal.'), {status:response.status, uncertain:Boolean(transaction && response.status >= 500)});
      }
      return data;
    } catch (error) {
      if (error.status) throw error;
      const uncertain = Boolean(transaction && !transaction.readOnly);
      throw Object.assign(new Error(uncertain
        ? 'Hasil penyimpanan belum terkonfirmasi. Coba ulang di sini; pencatatan yang sama tidak akan digandakan.'
        : 'Data belum dapat dimuat. Periksa koneksi dan pastikan server Beeloft berjalan.'), {uncertain});
    } finally { clearTimeout(timeout); }
  }
}
