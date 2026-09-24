// Apply the two small preferences before styles paint; custom blobs load from IndexedDB.
try {
  const root = document.documentElement;
  root.dataset.theme = localStorage.getItem('beeloft.theme') === 'dark' ? 'dark' : 'light';
  root.dataset.wallpaper = localStorage.getItem('beeloft.wallpaper') === 'mist' ? 'mist' : 'landscape';
} catch {}
