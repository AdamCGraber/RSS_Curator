import type { NextApiRequest, NextApiResponse } from "next";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const ENABLE_ADMIN_ACTIONS = process.env.ENABLE_ADMIN_ACTIONS === "true";

function buildRequestBody(req: NextApiRequest) {
  if (typeof req.body === "string") {
    return req.body.trim().length ? req.body : "{}";
  }

  if (req.body && typeof req.body === "object" && Object.keys(req.body).length > 0) {
    return JSON.stringify(req.body);
  }

  return "{}";
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  res.setHeader("Cache-Control", "no-store");

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  if (!ENABLE_ADMIN_ACTIONS && process.env.NODE_ENV === "production") {
    console.warn("Admin delete-all disabled in production.");
    return res.status(403).json({ error: "Disabled" });
  }

  try {
    const upstream = await fetch(`${BACKEND_URL}/admin/sources/delete-all`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(req.headers.authorization ? { authorization: req.headers.authorization } : {}),
        ...(req.headers.cookie ? { cookie: req.headers.cookie } : {})
      },
      body: buildRequestBody(req)
    });

    const contentType = upstream.headers.get("content-type");
    const bodyText = await upstream.text();

    if (contentType) {
      res.setHeader("Content-Type", contentType);
    }

    return res.status(upstream.status).send(bodyText);
  } catch (error: any) {
    console.error("Failed to reach backend for delete-all sources.", error);
    return res.status(502).json({
      error: "Backend unreachable",
      detail: String(error?.message ?? error),
      backend: BACKEND_URL
    });
  }
}
