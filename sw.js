/* ==========================================================================
 * 20260815_NurseExamApp_V1.00 / sw.js（Service Worker）
 * 完全オフライン動作 ＆ 自動バージョン更新
 *
 * 【改修時の手順】
 *   コードを直したら CACHE_NAME の版番号を必ず上げること。
 *   版番号が変わると、次回起動時にバックグラウンドで新コードを取得し、
 *   「新しいバージョンが利用可能です。更新しますか？」を自動表示する。
 *
 * 【資産を2群に分けている理由】
 *   cache.addAll() は1件でも失敗すると全体が reject され、
 *   インストールごと失敗してオフライン動作が丸ごと死ぬ。
 *   そこで、無いとアプリが動かない CORE だけを addAll で厳格に取得し、
 *   図解エンジン（3.3MB）などの OPTIONAL は個別に best-effort で取る。
 *   OPTIONAL が落ちても本体のオフライン動作は成立する。
 * ========================================================================== */

const CACHE_NAME = 'v1.25.0';
const RUNTIME    = 'runtime-' + CACHE_NAME;

/* 無いとアプリが起動しない資産。1件でも取れなければインストールを失敗させる。 */
const CORE_ASSETS = [
  './',
  './index.html',
  './styles.css',
  './questions.js',
  './storage.js',
  './scheduler.js',
  './drive.js',
  './20260815_main_part1_V1.25.js',
  './20260815_main_part2_V1.23.js',
  './about.html',
  './privacy.html',
  './terms.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-192.png',
  './icons/icon-maskable-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon-32.png',
  './icons/ogp.png'
];

/* 取れなくても本体は動く資産（図解エンジンなど） */
const OPTIONAL_ASSETS = [
  './vendor/mermaid.min.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(CORE_ASSETS);
    await Promise.allSettled(
      OPTIONAL_ASSETS.map((url) => cache.add(url).catch(() => null))
    );
    /* 自動では有効化しない。ユーザーが更新ダイアログで承諾したときだけ
       SKIP_WAITING を受け取って切り替える（学習中の画面を壊さないため）。 */
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k !== CACHE_NAME && k !== RUNTIME)
          .map((k) => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports && event.ports[0] && event.ports[0].postMessage({ cache: CACHE_NAME });
  }
  /* 図解エンジンを任意のタイミングで事前ダウンロードさせる口 */
  if (event.data && event.data.type === 'PRECACHE_OPTIONAL') {
    event.waitUntil((async () => {
      const cache = await caches.open(CACHE_NAME);
      await Promise.allSettled(OPTIONAL_ASSETS.map((u) => cache.add(u).catch(() => null)));
    })());
  }
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') { return; }

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) { return; }   /* 外部は素通し */

  /* 画面遷移：ネットワーク優先。落ちたらキャッシュ済みの index.html を返す。
     SPAなので、どのURLで開かれてもシェルを返せばアプリが起動する。 */
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const cache = await caches.open(RUNTIME);
        cache.put(req, fresh.clone());
        return fresh;
      } catch (e) {
        const cached = await caches.match(req);
        return cached || await caches.match('./index.html') || Response.error();
      }
    })());
    return;
  }

  /* 静的資産：キャッシュ優先 ＋ 取得できたら実行時キャッシュへ追加。
     オフラインでの起動速度を最優先する。 */
  event.respondWith((async () => {
    const cached = await caches.match(req, { ignoreSearch: false });
    if (cached) { return cached; }
    try {
      const fresh = await fetch(req);
      if (fresh && fresh.status === 200 && fresh.type === 'basic') {
        const cache = await caches.open(RUNTIME);
        cache.put(req, fresh.clone());
      }
      return fresh;
    } catch (e) {
      const fallback = await caches.match('./index.html');
      return fallback || new Response('', { status: 504, statusText: 'offline' });
    }
  })());
});
