export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') { res.status(200).end(); return; }

  const endpoint = req.query.endpoint;
  if (!endpoint) { res.status(400).json({ error: 'Missing endpoint' }); return; }

  const CANVAS_TOKEN = "2174~eerBfnZCPu3wGDBAEa3eYUATQ3nZKM48cJXBaGMNuCLVQhmEcaaaATPYFtvAJNV2";
  const CANVAS_URL = "katyisd.instructure.com";

  try {
    const r = await fetch(`https://${CANVAS_URL}/api/v1${endpoint}`, {
      headers: { 'Authorization': `Bearer ${CANVAS_TOKEN}` }
    });
    const data = await r.json();
    res.status(r.status).json(data);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}
