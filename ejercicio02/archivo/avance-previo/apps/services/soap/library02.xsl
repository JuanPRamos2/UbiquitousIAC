<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:lib="https://example.com/library"
    exclude-result-prefixes="lib">

  <xsl:output method="html" version="1.0" encoding="UTF-8" indent="yes"/>

  <xsl:template match="/">
    <html>
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Catálogo de libros</title>
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&amp;display=swap');

          :root {
            --bg: #f4f7fb;
            --panel: #ffffff;
            --text: #132238;
            --muted: #5d6b82;
            --primary: #1d4ed8;
            --primary-soft: #dbeafe;
            --accent: #f59e0b;
            --border: #e2e8f0;
            --shadow: 0 18px 38px rgba(15, 23, 42, 0.12);
          }

          * { box-sizing: border-box; }

          body {
            margin: 0;
            font-family: 'Inter', Arial, sans-serif;
            background:
              radial-gradient(circle at top, rgba(29, 78, 216, 0.08), transparent 35%),
              var(--bg);
            color: var(--text);
          }

          .page {
            max-width: 1280px;
            margin: 0 auto;
            padding: 48px 24px 72px;
          }

          .hero {
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 20px;
            margin-bottom: 28px;
            flex-wrap: wrap;
          }

          .eyebrow {
            display: inline-block;
            padding: 8px 12px;
            border-radius: 999px;
            background: var(--primary-soft);
            color: var(--primary);
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
          }

          h1 {
            margin: 12px 0 8px;
            font-size: clamp(2.2rem, 4vw, 4rem);
            line-height: 1.05;
            letter-spacing: -0.06em;
          }

          .subtitle {
            margin: 0;
            color: var(--muted);
            font-size: 1.05rem;
          }

          .stats {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
          }

          .stats span {
            display: inline-flex;
            align-items: center;
            padding: 10px 14px;
            border: 1px solid var(--border);
            border-radius: 999px;
            background: rgba(255,255,255,0.7);
            color: var(--muted);
            font-size: 0.86rem;
            font-weight: 600;
          }

          .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 24px;
          }

          .card {
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border: 1px solid var(--border);
            border-radius: 22px;
            background: var(--panel);
            box-shadow: var(--shadow);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
          }

          .card:hover {
            transform: translateY(-6px);
            box-shadow: 0 22px 42px rgba(15, 23, 42, 0.16);
          }

          .cover {
            display: block;
            width: 100%;
            height: 300px;
            object-fit: cover;
            background: linear-gradient(135deg, #dbeafe, #f8fafc);
            border-bottom: 1px solid var(--border);
          }

          .content {
            display: flex;
            flex: 1;
            flex-direction: column;
            padding: 20px 20px 18px;
          }

          .meta-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
          }

          .category {
            display: inline-flex;
            align-items: center;
            padding: 6px 10px;
            border-radius: 999px;
            background: #eef2ff;
            color: #3730a3;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
          }

          .price {
            color: var(--primary);
            font-size: 1.15rem;
            font-weight: 800;
          }

          h2 {
            margin: 0 0 12px;
            font-size: 1.62rem;
            line-height: 1.25;
            letter-spacing: -0.04em;
          }

          .details {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px 14px;
            margin: 0 0 16px;
            padding: 12px 0;
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            color: var(--muted);
            font-size: 0.8rem;
          }

          .details strong {
            color: var(--text);
          }

          .tag-list,
          .concept-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 6px;
          }

          .tag {
            display: inline-block;
            padding: 7px 10px;
            border-radius: 999px;
            background: #ecfeff;
            color: #0f766e;
            font-size: 0.74rem;
            font-weight: 600;
          }

          .section-label {
            display: block;
            margin-top: 16px;
            margin-bottom: 8px;
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.1em;
            text-transform: uppercase;
          }

          .concept {
            flex: 1 1 100%;
            margin-top: 8px;
            padding: 10px 12px;
            border-left: 3px solid var(--accent);
            background: #fffaf0;
            border-radius: 10px;
          }

          .concept strong {
            display: block;
            margin-bottom: 4px;
            color: var(--text);
            font-size: 0.8rem;
          }

          .concept span {
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.5;
          }

          @media (max-width: 640px) {
            .page { padding: 28px 16px 52px; }
            .details { grid-template-columns: 1fr; }
            .cover { height: 260px; }
          }
        </style>
      </head>
      <body>
        <div class="page">
          <div class="hero">
            <div>
              <span class="eyebrow">Biblioteca</span>
              <h1>Catálogo de libros</h1>
              <p class="subtitle">Colección curada con obras destacadas, temas relevantes y portadas visuales.</p>
            </div>
            <div class="stats">
              <span><strong><xsl:value-of select="count(lib:library/lib:books/lib:book)"/></strong> títulos</span>
              <span>XML + XSL</span>
            </div>
          </div>

          <div class="cards">
            <xsl:for-each select="lib:library/lib:books/lib:book">
              <article class="card">
                <xsl:variable name="imageUrl" select="lib:images/lib:image[1]"/>
                <img class="cover" alt="{
                    normalize-space(lib:images/lib:image[1]/@alt)
                  }" src="{
                    normalize-space($imageUrl)
                  }"/>

                <div class="content">
                  <div class="meta-row">
                    <span class="category"><xsl:value-of select="lib:category"/></span>
                    <span class="price">
                      $<xsl:value-of select="format-number(lib:price, '0.00')"/>
                    </span>
                  </div>

                  <h2><xsl:value-of select="lib:title"/></h2>

                  <div class="details">
                    <div><strong>Autor:</strong> <xsl:value-of select="lib:authors/lib:author"/></div>
                    <div><strong>Año:</strong> <xsl:value-of select="lib:publicationYear"/></div>
                    <div><strong>ISBN:</strong> <xsl:value-of select="lib:isbn"/></div>
                    <div><strong>Stock:</strong> <xsl:value-of select="lib:stock"/></div>
                    <div><strong>Formato:</strong> <xsl:value-of select="lib:format"/></div>
                    <div><strong>Moneda:</strong> <xsl:value-of select="lib:price/@currency"/></div>
                  </div>

                  <div>
                    <span class="section-label">Géneros</span>
                    <div class="tag-list">
                      <xsl:for-each select="lib:genres/lib:genre">
                        <span class="tag"><xsl:value-of select="."/></span>
                      </xsl:for-each>
                    </div>
                  </div>

                  <div>
                    <span class="section-label">Conceptos clave</span>
                    <div class="concept-list">
                      <xsl:for-each select="lib:concepts/lib:concept">
                        <div class="concept">
                          <strong><xsl:value-of select="@name"/></strong>
                          <span><xsl:value-of select="lib:definition"/></span>
                        </div>
                      </xsl:for-each>
                    </div>
                  </div>
                </div>
              </article>
            </xsl:for-each>
          </div>
        </div>
      </body>
    </html>
  </xsl:template>

</xsl:stylesheet>
