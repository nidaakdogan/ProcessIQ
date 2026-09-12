import { Document, Packer, Paragraph, HeadingLevel, TextRun, AlignmentType } from 'docx'
import { jsPDF } from 'jspdf'
import * as XLSX from 'xlsx'
import type { ExecutiveSummary } from '@/lib/api'
import { formatDateTimeLong } from '@/lib/utils'

export type ExportFormat = 'pdf' | 'docx' | 'xlsx' | 'md'

function metaLines(report: ExecutiveSummary) {
  return {
    brand: 'ProcessIQ',
    title: 'AI Yönetici Özeti',
    generated: formatDateTimeLong(report.generated_at),
    period: report.period_label,
    periodRange: report.period_range_label || '',
    project: report.project_name || 'Tüm Projeler',
    records: report.records_scanned,
    confidence: report.confidence ?? null,
    lastUpdated: formatDateTimeLong(report.last_updated || report.generated_at),
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function fileBase(report: ExecutiveSummary) {
  const day = (report.generated_at || '').slice(0, 10) || 'rapor'
  const period = report.period || 'week'
  return `ProcessIQ-Yonetici-Ozeti-${period}-${day}`
}

function trendChange(metric: {
  change_display?: string
  delta: string
}) {
  return metric.change_display || metric.delta
}

function trendRows(report: ExecutiveSummary) {
  const t = report.trends
  return [
    ['Başarısız Test', t.failed_tests],
    ['Kritik Bug', t.critical_bugs],
    ['Tamamlanan Görev', t.completed_tasks],
    ['Kalite Skoru', t.quality_score],
  ] as const
}

export function buildMarkdown(report: ExecutiveSummary): string {
  const m = metaLines(report)
  const o = report.overview
  const lines: string[] = [
    `# ${m.brand} — ${m.title}`,
    '',
    `**Oluşturulma:** ${m.generated}`,
    `**Rapor Dönemi:** ${m.period}${m.periodRange ? ` (${m.periodRange})` : ''}`,
    `**Proje:** ${m.project}`,
    `**Analiz Edilen Kayıt:** ${m.records}`,
    `**Son Güncelleme:** ${m.lastUpdated}`,
    ...(m.confidence != null ? [`**AI Güven Skoru:** %${m.confidence}`] : []),
    '',
    '---',
    '',
    '## Genel Durum',
    '',
    `| Metrik | Değer |`,
    `| --- | --- |`,
    `| Tamamlanan görev | ${o.completed_tasks} |`,
    `| Yeni açılan bug | ${o.new_bugs} |`,
    `| Başarısız test | ${o.failed_tests} |`,
    `| Kalite skoru | ${o.quality_score} (${o.quality_label}) |`,
    `| Release durumu | ${o.release_status} |`,
    '',
    o.quality_assessment,
    '',
    '## Kritik Gelişmeler',
    '',
  ]
  for (const item of report.critical_developments) {
    lines.push(`- **${item.title}:** ${item.detail}`)
  }
  lines.push('', '## AI Değerlendirmesi', '', report.assessment, '')
  if (m.confidence != null) {
    lines.push(`AI Güven Skoru: %${m.confidence}`, '')
  }
  lines.push('## AI Önerileri', '')
  report.recommendations.forEach((r, i) => lines.push(`${i + 1}. ${r}`))
  lines.push('', '## Trend Analizi', '', `${report.trends.period_label} ile karşılaştırma:`, '')
  lines.push('| Metrik | Önceki Dönem | Bu Dönem | Değişim |')
  lines.push('| --- | ---: | ---: | --- |')
  for (const [label, metric] of trendRows(report)) {
    lines.push(
      `| ${label} | ${metric.previous} | ${metric.current} | ${trendChange(metric)} |`,
    )
  }
  if (report.trends.commentary) {
    lines.push('', '### AI Trend Yorumu', '', report.trends.commentary)
  }
  if (report.priorities?.length) {
    lines.push('', '## AI Öncelikleri', '')
    report.priorities.forEach((p, i) => lines.push(`${i + 1}. ${p}`))
  }
  lines.push('', '---', '', `*${m.brand} · Yapay Zekâ Destekli Yazılım Süreç Analiz Platformu*`, '')
  return lines.join('\n')
}

export async function exportExecutiveReport(
  report: ExecutiveSummary,
  format: ExportFormat,
): Promise<void> {
  const base = fileBase(report)
  const m = metaLines(report)
  const o = report.overview

  if (format === 'md') {
    downloadBlob(new Blob([buildMarkdown(report)], { type: 'text/markdown;charset=utf-8' }), `${base}.md`)
    return
  }

  if (format === 'xlsx') {
    const wb = XLSX.utils.book_new()
    const cover = [
      ['ProcessIQ'],
      ['AI Yönetici Özeti'],
      [],
      ['Oluşturulma', m.generated],
      ['Rapor Dönemi', m.period],
      ['Dönem Aralığı', m.periodRange],
      ['Proje', m.project],
      ['Analiz Edilen Kayıt', m.records],
      ['Son Güncelleme', m.lastUpdated],
      ['AI Güven Skoru', m.confidence != null ? `%${m.confidence}` : '—'],
    ]
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(cover), 'Kapak')

    const overview = [
      ['Metrik', 'Değer'],
      ['Tamamlanan görev', o.completed_tasks],
      ['Yeni açılan bug', o.new_bugs],
      ['Başarısız test', o.failed_tests],
      ['Kalite skoru', `${o.quality_score} (${o.quality_label})`],
      ['Release durumu', o.release_status],
      ['Kalite değerlendirmesi', o.quality_assessment],
    ]
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(overview), 'Genel Durum')

    const critical = [
      ['Başlık', 'Detay'],
      ...report.critical_developments.map((c) => [c.title, c.detail]),
    ]
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(critical), 'Kritik Gelişmeler')

    XLSX.utils.book_append_sheet(
      wb,
      XLSX.utils.aoa_to_sheet([['AI Değerlendirmesi'], [report.assessment]]),
      'AI Değerlendirme',
    )

    const recs = [['#', 'Öneri'], ...report.recommendations.map((r, i) => [i + 1, r])]
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(recs), 'AI Önerileri')

    const trends = [
      ['Metrik', 'Önceki Dönem', 'Bu Dönem', 'Değişim'],
      ...trendRows(report).map(([label, metric]) => [
        label,
        metric.previous,
        metric.current,
        trendChange(metric),
      ]),
      ...(report.trends.commentary
        ? [[], ['AI Trend Yorumu', report.trends.commentary]]
        : []),
    ]
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(trends), 'Trend')

    if (report.priorities?.length) {
      const pri = [['#', 'Öncelik'], ...report.priorities.map((p, i) => [i + 1, p])]
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(pri), 'AI Öncelikleri')
    }

    XLSX.writeFile(wb, `${base}.xlsx`)
    return
  }

  if (format === 'docx') {
    const children: Paragraph[] = [
      new Paragraph({
        children: [new TextRun({ text: m.brand, bold: true, size: 36, color: '0F2747' })],
      }),
      new Paragraph({
        text: m.title,
        heading: HeadingLevel.HEADING_1,
      }),
      new Paragraph({ children: [new TextRun({ text: `Oluşturulma: ${m.generated}`, size: 20 })] }),
      new Paragraph({
        children: [
          new TextRun({
            text: `Rapor Dönemi: ${m.period}${m.periodRange ? ` (${m.periodRange})` : ''}`,
            size: 20,
          }),
        ],
      }),
      new Paragraph({ children: [new TextRun({ text: `Proje: ${m.project}`, size: 20 })] }),
      new Paragraph({
        children: [new TextRun({ text: `Analiz Edilen Kayıt: ${m.records}`, size: 20 })],
      }),
      new Paragraph({
        children: [new TextRun({ text: `Son Güncelleme: ${m.lastUpdated}`, size: 20 })],
      }),
      ...(m.confidence != null
        ? [
            new Paragraph({
              children: [new TextRun({ text: `AI Güven Skoru: %${m.confidence}`, size: 20 })],
            }),
          ]
        : []),
      new Paragraph({ text: '' }),
      new Paragraph({ text: 'Genel Durum', heading: HeadingLevel.HEADING_2 }),
      new Paragraph({ text: `Tamamlanan görev: ${o.completed_tasks}` }),
      new Paragraph({ text: `Yeni açılan bug: ${o.new_bugs}` }),
      new Paragraph({ text: `Başarısız test: ${o.failed_tests}` }),
      new Paragraph({ text: `Kalite skoru: ${o.quality_score} (${o.quality_label})` }),
      new Paragraph({ text: `Release durumu: ${o.release_status}` }),
      new Paragraph({ text: o.quality_assessment }),
      new Paragraph({ text: '' }),
      new Paragraph({ text: 'Kritik Gelişmeler', heading: HeadingLevel.HEADING_2 }),
      ...report.critical_developments.map(
        (c) => new Paragraph({ text: `${c.title}: ${c.detail}`, bullet: { level: 0 } }),
      ),
      new Paragraph({ text: '' }),
      new Paragraph({ text: 'AI Değerlendirmesi', heading: HeadingLevel.HEADING_2 }),
      new Paragraph({ text: report.assessment }),
      new Paragraph({ text: '' }),
      new Paragraph({ text: 'AI Önerileri', heading: HeadingLevel.HEADING_2 }),
      ...report.recommendations.map(
        (r, i) => new Paragraph({ text: `${i + 1}. ${r}` }),
      ),
      new Paragraph({ text: '' }),
      new Paragraph({ text: 'Trend Analizi', heading: HeadingLevel.HEADING_2 }),
      new Paragraph({ text: `${report.trends.period_label} ile karşılaştırma` }),
      ...trendRows(report).map(
        ([label, metric]) =>
          new Paragraph({
            text: `${label}: ${metric.previous} → ${metric.current} (${trendChange(metric)})`,
          }),
      ),
      ...(report.trends.commentary
        ? [
            new Paragraph({ text: '' }),
            new Paragraph({
              children: [new TextRun({ text: 'AI Trend Yorumu', bold: true })],
            }),
            new Paragraph({ text: report.trends.commentary }),
          ]
        : []),
    ]
    if (report.priorities?.length) {
      children.push(
        new Paragraph({ text: '' }),
        new Paragraph({ text: 'AI Öncelikleri', heading: HeadingLevel.HEADING_2 }),
        ...report.priorities.map((p, i) => new Paragraph({ text: `${i + 1}. ${p}` })),
      )
    }
    children.push(
      new Paragraph({ text: '' }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({
            text: 'ProcessIQ · Yapay Zekâ Destekli Yazılım Süreç Analiz Platformu',
            italics: true,
            size: 18,
            color: '64748B',
          }),
        ],
      }),
    )
    const doc = new Document({ sections: [{ children }] })
    const blob = await Packer.toBlob(doc)
    downloadBlob(blob, `${base}.docx`)
    return
  }

  // PDF
  const doc = new jsPDF({ unit: 'pt', format: 'a4' })
  const margin = 48
  const pageW = doc.internal.pageSize.getWidth()
  const maxW = pageW - margin * 2
  let y = margin

  const ensureSpace = (need: number) => {
    if (y + need > doc.internal.pageSize.getHeight() - margin) {
      doc.addPage()
      y = margin
    }
  }

  const write = (text: string, opts?: { size?: number; bold?: boolean; color?: [number, number, number] }) => {
    const size = opts?.size ?? 11
    doc.setFont('helvetica', opts?.bold ? 'bold' : 'normal')
    doc.setFontSize(size)
    if (opts?.color) doc.setTextColor(...opts.color)
    else doc.setTextColor(15, 39, 71)
    const lines = doc.splitTextToSize(text, maxW)
    ensureSpace(lines.length * (size + 4) + 4)
    doc.text(lines, margin, y)
    y += lines.length * (size + 4) + 6
  }

  write('ProcessIQ', { size: 18, bold: true, color: [15, 39, 71] })
  write('AI Yönetici Özeti', { size: 14, bold: true })
  y += 4
  write(`Olusturulma: ${m.generated}`, { size: 10, color: [100, 116, 139] })
  write(`Rapor Donemi: ${m.period}${m.periodRange ? ` (${m.periodRange})` : ''}`, { size: 10 })
  write(`Proje: ${m.project}`, { size: 10 })
  write(`Analiz Edilen Kayit: ${m.records}`, { size: 10 })
  write(`Son Guncelleme: ${m.lastUpdated}`, { size: 10 })
  if (m.confidence != null) write(`AI Guven Skoru: %${m.confidence}`, { size: 10 })
  y += 8

  write('Genel Durum', { size: 13, bold: true })
  write(`Tamamlanan gorev: ${o.completed_tasks}`)
  write(`Yeni acilan bug: ${o.new_bugs}`)
  write(`Basarisiz test: ${o.failed_tests}`)
  write(`Kalite skoru: ${o.quality_score} (${o.quality_label})`)
  write(`Release durumu: ${o.release_status}`)
  write(o.quality_assessment)
  y += 6

  write('Kritik Gelismeler', { size: 13, bold: true })
  for (const c of report.critical_developments) {
    write(`- ${c.title}: ${c.detail}`)
  }
  y += 6

  write('AI Degerlendirmesi', { size: 13, bold: true })
  write(report.assessment)
  y += 6

  write('AI Onerileri', { size: 13, bold: true })
  report.recommendations.forEach((r, i) => write(`${i + 1}. ${r}`))
  y += 6

  write('Trend Analizi', { size: 13, bold: true })
  write(`${report.trends.period_label} ile karsilastirma`)
  for (const [label, metric] of trendRows(report)) {
    write(
      `${label}: ${metric.previous} -> ${metric.current} (${trendChange(metric)})`,
    )
  }
  if (report.trends.commentary) {
    y += 4
    write('AI Trend Yorumu', { size: 11, bold: true })
    write(report.trends.commentary)
  }

  if (report.priorities?.length) {
    y += 6
    write('AI Oncelikleri', { size: 13, bold: true })
    report.priorities.forEach((p, i) => write(`${i + 1}. ${p}`))
  }

  y += 12
  write('ProcessIQ - Yapay Zeka Destekli Yazilim Surec Analiz Platformu', {
    size: 9,
    color: [100, 116, 139],
  })

  doc.save(`${base}.pdf`)
}
