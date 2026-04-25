"""Miscellaneous utility endpoints.

This module provides a small set of helper routes (e.g., a quick way to see the
client's IP and the server's local IP) for debugging / local development.
"""

import socket
from datetime import date
from flask import Blueprint, Response, make_response, request, render_template, render_template_string, redirect, session, url_for

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/robots.txt")
def robots_txt():
    base = request.url_root.rstrip("/")
    content = f"""User-agent: *
Allow: /
Disallow: /admin
Disallow: /api/
Disallow: /dashboard
Disallow: /messages
Disallow: /notifications
Disallow: /profile
Disallow: /courses
Disallow: /library
Disallow: /ai
Disallow: /ip

Sitemap: {base}/sitemap.xml
"""
    return Response(content, mimetype="text/plain")


@misc_bp.route("/sitemap.xml")
def sitemap_xml():
    today = date.today().isoformat()
    base = request.url_root.rstrip("/")
    pages = [
        ("", "1.0", "daily"),
        ("/auth/login", "0.8", "monthly"),
        ("/auth/register", "0.8", "monthly"),
    ]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, priority, freq in pages:
        lines += [
            "  <url>",
            f"    <loc>{base}{path}</loc>",
            f"    <lastmod>{today}</lastmod>",
            f"    <changefreq>{freq}</changefreq>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ]
    lines.append("</urlset>")
    resp = make_response("\n".join(lines))
    resp.headers["Content-Type"] = "application/xml"
    return resp


@misc_bp.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("dashboard.feed"))
    return render_template("public/landing.html")


def get_server_local_ip() -> str:
    """Return a likely local IP address for this machine."""
    try:
        # This does not send any data; it's just used to pick the outbound interface.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback
        return socket.gethostbyname(socket.gethostname())


@misc_bp.route("/ip")
def show_ip():
    """Show client IP and (likely) server local IP."""
    client_ip = request.remote_addr or "unknown"
    server_ip = get_server_local_ip()

    return render_template_string(
        """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>IP Info</title>
            <style>
              body { font-family: system-ui, sans-serif; padding: 2rem; background: #f8fafc; }
              .card { max-width: 420px; margin: auto; padding: 1.75rem; border-radius: 16px; background: #fff;
                      box-shadow: 0 8px 22px rgba(0,0,0,.08); }
              h1 { margin-bottom: .75rem; font-size: 1.4rem; }
              dt { font-weight: 700; }
              dd { margin: .25rem 0 1rem 0; }
              a { color: #2563eb; text-decoration: none; }
            </style>
          </head>
          <body>
            <div class="card">
              <h1>IP Info</h1>
              <dl>
                <dt>Your (client) IP</dt>
                <dd><code>{{ client_ip }}</code></dd>
                <dt>Server local IP</dt>
                <dd><code>{{ server_ip }}</code></dd>
              </dl>
              <p>You can access this server from another device using:
                 <br /><code>http://{{ server_ip }}:5000</code></p>
              <p style="font-size:.85rem; color:#64748b;">Use <a href="/?lang=ar">?lang=ar</a>, <a href="/?lang=fr">?lang=fr</a> or <a href="/?lang=es">?lang=es</a> to switch languages.</p>
            </div>
          </body>
        </html>
        """,
        client_ip=client_ip,
        server_ip=server_ip,
    )
