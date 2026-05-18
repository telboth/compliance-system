#!/usr/bin/env node
'use strict';
/**
 * generate_dummy_invoice.js
 *
 * Lager en realistisk handels-faktura (PDF) for sanksjonsscreening-testing.
 * Rosneft er nevnt som faktisk sluttbruker i End-User Statement-seksjonen,
 * skjult litt under overflaten (liten skrift, formell legalspråk).
 *
 * Kjør: node generate_dummy_invoice.js
 * Output: dummy_invoice_rosneft.pdf (samme mappe)
 */

const fs   = require('fs');
const path = require('path');

// ─── PDF helpers ──────────────────────────────────────────────────────────────

/** Escape special characters in PDF string literals */
function esc(s) {
  return String(s)
    .replace(/\\/g, '\\\\')
    .replace(/\(/g,  '\\(')
    .replace(/\)/g,  '\\)');
}

// ─── Content stream builder ───────────────────────────────────────────────────

function buildStream() {
  const cmds = [];
  const p = (...args) => cmds.push(...args);

  // Absolute text at (x,y), font F1=Helvetica or FB=Helvetica-Bold
  const T = (x, y, size, font, str) =>
    p(`BT /${font} ${size} Tf 1 0 0 1 ${x} ${y} Tm (${esc(str)}) Tj ET`);

  // Horizontal rule
  const HL = (x1, y, x2, lw = 0.4) =>
    p(`${lw} w ${x1} ${y} m ${x2} ${y} l S`);

  // Filled rectangle, then reset to black
  const RECT = (x, y, w, h, r, g, b) => {
    p(`${r} ${g} ${b} rg`);
    p(`${x} ${y} ${w} ${h} re f`);
    p('0 0 0 rg');
  };

  // ── A4 page: 595 × 842 pt, origin bottom-left ─────────────────────────────

  // Navy header bar
  RECT(0, 795, 595, 47, 0.10, 0.18, 0.38);
  p('1 1 1 rg');
  T(36, 821, 14, 'FB', 'TechNord Instruments AS');
  T(36, 808, 7.5, 'F1', 'Drammensveien 288  |  NO-0283 Oslo, Norway  |  Org.nr: 913 872 614');
  T(36, 799, 7.5, 'F1', 'Tel: +47 22 13 78 00  |  export@technord.no  |  www.technord.no');
  T(380, 825, 16, 'FB', 'COMMERCIAL INVOICE');
  T(380, 812, 8.5, 'F1', 'Invoice no:  INV-2025-0847');
  T(380, 801, 8.5, 'F1', 'Invoice date:  14 March 2025');
  p('0 0 0 rg');

  // ── Address columns ────────────────────────────────────────────────────────
  let y = 780;
  T(36,  y, 7, 'FB', 'SELLER');
  T(215, y, 7, 'FB', 'BILL TO / BUYER');
  T(410, y, 7, 'FB', 'SHIP TO');
  y -= 4;  HL(36, y, 559);  y -= 10;

  const col = (lines, x, startY, lh = 10.5) =>
    lines.forEach((l, i) => l && T(x, startY - i * lh, 8, 'F1', l));

  col([
    'TechNord Instruments AS',
    'Drammensveien 288',
    'NO-0283 Oslo, Norway',
    'Tel: +47 22 13 78 00',
    'VAT: NO913872614MVA',
    'export@technord.no',
  ], 36, y);

  col([
    'EuroTech Solutions GmbH',
    'Hafenstrasse 42',
    'DE-20457 Hamburg',
    'Germany',
    'VAT: DE342871900',
    'h.mueller@eurotech-solutions.de',
  ], 215, y);

  col([
    'EuroTech Solutions GmbH',
    'c/o HH Bonded Warehouse',
    'Speicherstadt, Block W',
    'DE-20457 Hamburg',
    'Germany',
  ], 410, y);

  y -= 7 * 10.5;

  // ── Terms bar ─────────────────────────────────────────────────────────────
  HL(36, y, 559);
  RECT(36, y - 13, 523, 13, 0.93, 0.93, 0.93);
  T(38,  y - 9.5, 7.5, 'FB', 'Payment terms:');
  T(115, y - 9.5, 7.5, 'F1', 'T/T 30 days from B/L date');
  T(270, y - 9.5, 7.5, 'FB', 'Incoterms:');
  T(312, y - 9.5, 7.5, 'F1', 'DAP Hamburg (Incoterms 2020)');
  T(448, y - 9.5, 7.5, 'FB', 'Currency: EUR');
  y -= 15;

  RECT(36, y - 13, 523, 13, 0.96, 0.96, 0.96);
  T(38,  y - 9.5, 7.5, 'FB', 'Transport:');
  T(82,  y - 9.5, 7.5, 'F1', 'Sea freight (FCL)');
  T(185, y - 9.5, 7.5, 'FB', 'Country of origin:');
  T(258, y - 9.5, 7.5, 'F1', 'Norway (NO)');
  T(340, y - 9.5, 7.5, 'FB', 'Port of loading:');
  T(404, y - 9.5, 7.5, 'F1', 'Oslo (NOOSL)');
  T(466, y - 9.5, 7.5, 'FB', 'Port of discharge:');
  // intentionally wrapped:
  y -= 15;
  T(38,  y - 2,   7.5, 'F1', 'Hamburg (DEHAM)');
  T(185, y - 2,   7.5, 'FB', 'Vessel / Voyage:');
  T(248, y - 2,   7.5, 'F1', 'MV Atlantic Provider / VOY-2025-11W');
  T(448, y - 2,   7.5, 'FB', 'B/L ref: NOOSL-2025-08472');
  y -= 14;

  // ── Line items table ───────────────────────────────────────────────────────
  HL(36, y, 559, 0.5);
  RECT(36, y - 14, 523, 14, 0.10, 0.18, 0.38);
  p('1 1 1 rg');
  T(38,  y - 10, 7.5, 'FB', 'Description of Goods');
  T(278, y - 10, 7.5, 'FB', 'HS Code');
  T(326, y - 10, 7.5, 'FB', 'ECCN');
  T(366, y - 10, 7.5, 'FB', 'Qty');
  T(392, y - 10, 7.5, 'FB', 'Unit Price');
  T(458, y - 10, 7.5, 'FB', 'Total EUR');
  p('0 0 0 rg');
  y -= 16;

  const rows = [
    {
      d1: 'Precision Differential Pressure Measurement System',
      d2: 'Model: PMS-7400X  |  S/N: PMS-7400X-00291 / -00292  |  Mfr: TechNord',
      hs: '9026.20.20', eccn: '6A006.a',
      qty: '2 pcs', unit: '18,500.00', total: '37,000.00', shade: false,
    },
    {
      d1: 'Signal Conditioning Module SCM-400',
      d2: 'Rack-mount, 24 VDC, accessory for PMS-7400X series. CE marked.',
      hs: '9032.89.00', eccn: 'EAR99',
      qty: '2 pcs', unit: '3,200.00', total: '6,400.00', shade: true,
    },
    {
      d1: 'On-site Installation & Commissioning Package',
      d2: 'Incl. 3-day field service, calibration to ISO 9001, documentation set',
      hs: 'N/A (service)', eccn: 'EAR99',
      qty: '1 lot', unit: '4,450.00', total: '4,450.00', shade: false,
    },
  ];

  rows.forEach(row => {
    if (row.shade) RECT(36, y - 22, 523, 24, 0.95, 0.95, 0.95);
    T(38,  y - 8,  8,   'F1', row.d1);
    T(38,  y - 17, 7,   'F1', row.d2);
    T(278, y - 8,  7.5, 'F1', row.hs);
    T(326, y - 8,  7.5, 'F1', row.eccn);
    T(366, y - 8,  7.5, 'F1', row.qty);
    T(392, y - 8,  7.5, 'F1', row.unit);
    T(458, y - 8,  7.5, 'F1', row.total);
    y -= 26;
  });

  // Total row
  HL(36, y + 4, 559, 0.6);
  RECT(36, y - 13, 523, 15, 0.10, 0.18, 0.38);
  p('1 1 1 rg');
  T(38,  y - 9, 9, 'FB', 'TOTAL INVOICE VALUE');
  T(450, y - 9, 9, 'FB', 'EUR 47,850.00');
  p('0 0 0 rg');
  y -= 18;

  T(350, y, 7.5, 'F1', 'Goods:      EUR 43,400.00');  y -= 10;
  T(350, y, 7.5, 'F1', 'Services:   EUR  4,450.00');  y -= 10;
  T(350, y, 7.5, 'F1', 'Freight:    EUR      0.00  (prepaid by seller)');
  y -= 16;

  // ── Export certifications ──────────────────────────────────────────────────
  HL(36, y, 559, 0.4);  y -= 10;
  T(36, y, 8.5, 'FB', 'EXPORT CONTROL CERTIFICATIONS');  y -= 12;
  T(36, y, 7.5, 'F1', 'We hereby certify that this invoice is true, correct and complete, and that the goods');
  y -= 10;
  T(36, y, 7.5, 'F1', 'are correctly described herein. All items are of Norwegian commercial origin.');
  y -= 10;
  T(36, y, 7.5, 'F1', 'ECCN 6A006.a: Importer is responsible for EAR license determination. License Exception');
  y -= 10;
  T(36, y, 7.5, 'F1', 'GBS (15 CFR 740.4) or STA may be applicable. No items on US Munitions List (USML).');
  y -= 10;
  T(36, y, 7.5, 'F1', 'Norwegian export licence no. EKS-2025-01134 issued by UTENRIKSDEPARTEMENTET / DEKSA.');
  y -= 16;

  // ── End-user statement — Rosneft is here ──────────────────────────────────
  HL(36, y, 559, 0.4);
  RECT(36, y - 58, 523, 56, 0.98, 0.96, 0.90);
  y -= 9;
  T(38, y, 8, 'FB', 'END-USER STATEMENT  (ref. EuroTech Compliance Procedure ECP-2024-11, sec. 3.2)');
  y -= 12;
  T(38, y, 7.5, 'F1', 'EuroTech Solutions GmbH, in its capacity as authorised trading agent and re-exporter,');
  y -= 10;
  T(38, y, 7.5, 'F1', 'hereby certifies pursuant to EC Reg. 2021/821 Art. 4 that the goods described in this');
  y -= 10;
  T(38, y, 7.5, 'F1', 'invoice are procured exclusively on behalf of the following confirmed end-user:');
  y -= 11;
  T(38, y, 8, 'FB', 'Rosneft Neftegas LLC');
  T(132, y, 7.5, 'F1',  '  Oktyabrsky District, Khanty-Mansiysk 628011, Russian Federation');
  y -= 10;
  T(38, y, 7.5, 'F1', 'Purpose of use: installation in hydrocarbon measurement systems, Priobskoye field ops.');
  y -= 10;
  T(38, y, 7, 'F1',
    'Technical liaison: S. Slatan  |  slatan.sanctionbuster@rosneft.com  |  Proj. ref: RN-PROJ-2025-441');
  y -= 20;

  // ── Signature block ────────────────────────────────────────────────────────
  HL(36, y, 280, 0.5);  HL(310, y, 559, 0.5);
  y -= 10;
  T(36,  y, 8, 'F1', 'Harald Eriksen');
  T(310, y, 8, 'F1', 'Date: 14 March 2025  |  Place: Oslo, Norway');
  y -= 10;
  T(36,  y, 7.5, 'F1', 'Export Compliance Manager');
  y -= 10;
  T(36,  y, 7.5, 'F1', 'TechNord Instruments AS');

  // ── Navy footer bar ────────────────────────────────────────────────────────
  RECT(0, 0, 595, 28, 0.10, 0.18, 0.38);
  p('1 1 1 rg');
  T(36, 18, 7, 'F1', 'TechNord Instruments AS  |  export@technord.no  |  www.technord.no');
  T(36,  9, 7, 'F1',
    'Bank: DNB Bank ASA  |  IBAN: NO93 8601 1117 947  |  SWIFT: DNBANOKKXXX  |  Page 1 of 1');
  p('0 0 0 rg');

  return cmds.join('\n');
}

// ─── PDF object assembler ─────────────────────────────────────────────────────

function buildPDF(stream) {
  const offsets = {};
  let src = '%PDF-1.4\n';

  function addObj(id, content) {
    offsets[id] = src.length;
    src += `${id} 0 obj\n${content}\nendobj\n`;
  }

  addObj(1, '<< /Type /Catalog /Pages 2 0 R >>');
  addObj(2, '<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
  addObj(3, [
    '<< /Type /Page',
    '   /Parent 2 0 R',
    '   /MediaBox [0 0 595 842]',
    '   /Contents 4 0 R',
    '   /Resources <<',
    '     /Font <<',
    '       /F1 5 0 R',
    '       /FB 6 0 R',
    '     >>',
    '   >>',
    '>>',
  ].join('\n'));

  const streamLen = Buffer.byteLength(stream, 'latin1');
  addObj(4, `<< /Length ${streamLen} >>\nstream\n${stream}\nendstream`);
  addObj(5, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>');
  addObj(6, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>');

  // Cross-reference table
  const xrefOffset = src.length;
  src += 'xref\n0 7\n';
  src += '0000000000 65535 f \n';
  for (let i = 1; i <= 6; i++) {
    src += offsets[i].toString().padStart(10, '0') + ' 00000 n \n';
  }
  src += 'trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n' + xrefOffset + '\n%%EOF\n';

  return src;
}

// ─── Main ─────────────────────────────────────────────────────────────────────

const stream  = buildStream();
const pdf     = buildPDF(stream);
const outPath = path.join(__dirname, 'dummy_invoice_rosneft.pdf');

fs.writeFileSync(outPath, pdf, 'latin1');
console.log('Created:', outPath);
console.log('Size:   ', pdf.length, 'bytes');
