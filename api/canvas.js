export const config = { runtime: 'edge' };

export default async function handler(req) {
  const url = new URL(req.url);
  const endpoint = url.searchParams.get('endpoint');
  
  if (!endpoint) {
    return new Response(JSON.stringify({ error: 'Missing endpoint' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  }

  const CANVAS_TOKEN = "2174~eerBfnZCPu3wGDBAEa3eYUATQ3nZKM48cJXBaGMNuCLVQhmEcaaaATPYFtvAJNV2";
  const CANVAS_URL = "katyisd.instructure.com";

  try {
    const r = await fetch(`https://${CANVAS_URL}/api/v1${endpoint}`, {
      headers: { 'Authorization': `Bearer ${CANVAS_TOKEN}` }
    });
    const data = await r.text();
    return new Response(data, {
      status: r.status,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  }
}
