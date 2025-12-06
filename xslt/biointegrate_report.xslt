<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" indent="yes" encoding="UTF-8"/>

<xsl:template match="/">
  <html>
  <head>
    <title>Reporte BioIntegrate</title>
    <style>
      body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background-color: #f8f9fa; color: #333; }
      h1 { text-align: center; color: #2c3e50; margin-bottom: 20px; }
      .summary { text-align: center; margin-bottom: 30px; font-style: italic; color: #666; }
      
      table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 40px; }
      th, td { padding: 12px 15px; border-bottom: 1px solid #ddd; }
      th { background-color: #f1f1f1; text-transform: uppercase; font-size: 12px; letter-spacing: 1px; text-align: left; }
      tr:hover { background-color: #f9f9f9; }
      
      .tag { display: inline-block; background: #e3f2fd; color: #0d47a1; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin: 1px; border: 1px solid #bbdefb; }
      .meta { font-size: 11px; color: #7f8c8d; display: block; margin-top: 2px; }
      .val-mono { font-family: 'Consolas', monospace; font-weight: bold; color: #2c3e50; }

      /* ESTILOS QUERY 2 (Waterfall) */
      .chart-cell { width: 400px; position: relative; border-left: 1px dashed #ccc; border-right: 1px dashed #ccc; }
      .axis-line { position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background-color: #333; z-index: 10; opacity: 0.3; }
      .bar-wrapper { display: flex; align-items: center; height: 18px; width: 100%; }
      .bar-pos { height: 100%; background-color: #e74c3c; margin-left: 50%; border-radius: 0 3px 3px 0; transition: width 0.3s ease; }
      .bar-neg { height: 100%; background-color: #27ae60; margin-right: 50%; margin-left: auto; border-radius: 3px 0 0 3px; transition: width 0.3s ease; }
      .val-text { font-family: 'Consolas', monospace; font-size: 11px; text-align: right; }
    </style>
  </head>
  <body>

    <xsl:choose>

        <xsl:when test="results/result[1]/statistics/log2_fc">
            <h1>Diferencial de Expresión: GBM vs LGG</h1>
            <p class="summary">
              Análisis de Log2 Fold Change. 
              <span style="color:#e74c3c"><strong>Barras Rojas (Derecha)</strong></span> = Mayor expresión en Glioblastoma (GBM).
              <span style="color:#27ae60"><strong>Barras Verdes (Izquierda)</strong></span> = Mayor expresión en Glioma de Bajo Grado (LGG).
            </p>

            <table>
              <thead>
                <tr>
                  <th>Gen</th>
                  <th>HGNC ID</th>
                  <th style="text-align:center">Log2 FC</th>
                  <th style="text-align:center">Visualización</th>
                  <th>Proteína (UniProt)</th>
                </tr>
              </thead>
              <tbody>
                <xsl:for-each select="results/result">
                  <xsl:sort select="statistics/log2_fc" data-type="number" order="descending"/>
                  
                  <tr>
                    <td><strong><xsl:value-of select="gene_symbol"/></strong></td>
                    <td style="font-size:12px; color:#777;"><xsl:value-of select="hgnc_id"/></td>
                    
                    <td class="val-text">
                      <xsl:value-of select="format-number(statistics/log2_fc, '0.00')"/>
                    </td>
                    
                    <td class="chart-cell">
                      <div class="axis-line"></div>
                      <div class="bar-wrapper">
                        <xsl:variable name="val" select="statistics/log2_fc"/>
                        <xsl:choose>
                          <xsl:when test="$val &gt; 0">
                            <div class="bar-pos">
                              <xsl:attribute name="style">width: <xsl:value-of select="($val div 16) * 50"/>%;</xsl:attribute>
                              <xsl:attribute name="title">Upregulated in GBM: <xsl:value-of select="$val"/></xsl:attribute>
                            </div>
                          </xsl:when>
                          <xsl:otherwise>
                            <div class="bar-neg">
                              <xsl:attribute name="style">width: <xsl:value-of select="(($val * -1) div 16) * 50"/>%;</xsl:attribute>
                              <xsl:attribute name="title">Upregulated in LGG: <xsl:value-of select="$val"/></xsl:attribute>
                            </div>
                          </xsl:otherwise>
                        </xsl:choose>
                      </div>
                    </td>
                    
                    <td>
                      <xsl:choose>
                        <xsl:when test="uniprot_annotation/protein_name/@is_null = 'true'">
                          <span style="color:#ccc; font-style:italic;">-</span>
                        </xsl:when>
                        <xsl:otherwise>
                          <div style="font-size:12px; font-weight:bold;"><xsl:value-of select="uniprot_annotation/protein_name"/></div>
                          <xsl:if test="uniprot_annotation/molecular_function_item">
                            <div style="margin-top:4px;">
                              <xsl:for-each select="uniprot_annotation/molecular_function_item">
                                <span class="tag"><xsl:value-of select="."/></span>
                              </xsl:for-each>
                            </div>
                          </xsl:if>
                        </xsl:otherwise>
                      </xsl:choose>
                    </td>
                  </tr>
                </xsl:for-each>
              </tbody>
            </table>
        </xsl:when>

        <xsl:when test="results/result[1]/membrane_annotations">
            <h1>Proteínas de Membrana en Cáncer (Cobertura)</h1>
            <p class="summary">Porcentaje de pacientes positivos por tipo de tumor.</p>
            <table>
                <thead>
                    <tr>
                        <th>Proteína (UniProt)</th>
                        <th>Gen Asociado</th>
                        <th style="width:30%">Anotaciones de Membrana</th>
                        <th style="text-align:center">Cobertura LGG</th>
                        <th style="text-align:center">Cobertura GBM</th>
                    </tr>
                </thead>
                <tbody>
                    <xsl:for-each select="results/result">
                        <xsl:sort select="lgg/coverage" data-type="number" order="descending"/>
                        <tr>
                            <td>
                                <strong><xsl:value-of select="uniprot_id"/></strong><br/>
                                <span class="meta"><xsl:value-of select="entry_name"/></span>
                            </td>
                            <td>
                                <span class="val-mono"><xsl:value-of select="gene_symbol"/></span><br/>
                                <span class="meta"><xsl:value-of select="hgnc_id"/></span>
                            </td>
                            <td>
                                <xsl:for-each select="membrane_annotations/membrane_annotation">
                                    <div class="tag" style="background:#fff3e0; color:#e65100; border-color:#ffe0b2;">
                                        <xsl:value-of select="substring(., 1, 60)"/><xsl:if test="string-length(.) &gt; 60">...</xsl:if>
                                    </div>
                                </xsl:for-each>
                            </td>
                            <td style="text-align:center">
                                <div class="val-mono" style="font-size:16px;">
                                    <xsl:value-of select="format-number(lgg/coverage * 100, '0')"/>%
                                </div>
                                <span class="meta"><xsl:value-of select="lgg/positive_cases"/> / <xsl:value-of select="lgg/n_cases"/></span>
                            </td>
                            <td style="text-align:center">
                                <div class="val-mono" style="font-size:16px;">
                                    <xsl:value-of select="format-number(gbm/coverage * 100, '0')"/>%
                                </div>
                                <span class="meta"><xsl:value-of select="gbm/positive_cases"/> / <xsl:value-of select="gbm/n_cases"/></span>
                            </td>
                        </tr>
                    </xsl:for-each>
                </tbody>
            </table>
        </xsl:when>

        <xsl:otherwise>
            <h1>Genes con Alta Expresión en LGG (>500 TPM)</h1>
            <p class="summary">Listado de genes altamente expresados y su correspondencia en UniProt.</p>
            <table>
                <thead>
                    <tr>
                        <th>Gen (HGNC)</th>
                        <th>Identificadores</th>
                        <th style="text-align:right">TPM Medio</th>
                        <th>Anotación Funcional (UniProt)</th>
                    </tr>
                </thead>
                <tbody>
                    <xsl:for-each select="results/result">
                        <xsl:sort select="mean_tpm_unstranded" data-type="number" order="descending"/>
                        <tr>
                            <td>
                                <div style="font-size:16px; font-weight:bold; color:#2c3e50;"><xsl:value-of select="symbol"/></div>
                                <span class="meta"><xsl:value-of select="hgnc_id"/></span>
                            </td>
                            <td>
                                <div class="meta">Ensembl: <strong style="color:#333"><xsl:value-of select="ensembl_gene_id"/></strong></div>
                                <div class="meta">UniProt IDs: <xsl:value-of select="count(uniprot_ids/uniprot_id)"/></div>
                            </td>
                            <td style="text-align:right">
                                <div class="val-mono" style="font-size:15px; color:#27ae60;">
                                    <xsl:value-of select="format-number(mean_tpm_unstranded, '#,###.00')"/>
                                </div>
                                <span class="meta">Transcripts Per Million</span>
                            </td>
                            <td>
                                <xsl:for-each select="uniprot_annotations/uniprot_annotation">
                                    <div style="margin-bottom:8px; border-left: 2px solid #3498db; padding-left:8px;">
                                        <strong><xsl:value-of select="uniprot_id"/></strong>: <xsl:value-of select="protein_name"/>
                                        <br/>
                                        <span class="meta">Longitud: <xsl:value-of select="protein_length"/> aa</span>
                                        <xsl:if test="function_cc">
                                            <div style="font-size:11px; color:#555; margin-top:2px; font-style:italic;">
                                                <xsl:value-of select="substring(function_cc, 1, 120)"/>...
                                            </div>
                                        </xsl:if>
                                    </div>
                                </xsl:for-each>
                            </td>
                        </tr>
                    </xsl:for-each>
                </tbody>
            </table>
        </xsl:otherwise>

    </xsl:choose>
  </body>
  </html>
</xsl:template>
</xsl:stylesheet>