import os
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_receipt(team, players, contact, amount, receipt_id, match_datetime, tournament_name):
    os.makedirs("receipts", exist_ok=True)
    qr_path = f"receipts/{receipt_id}_qr.png"
    logo_path = "logo.png"
    pdf_path = f"receipts/{receipt_id}_receipt.pdf"

    qr = qrcode.make(receipt_id).resize((100, 100))
    qr.save(qr_path)

    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name="Title", fontSize=16, leading=20, alignment=1, textColor=colors.HexColor("#1F4E79"))
    section_heading = ParagraphStyle(name="Heading", fontSize=13, leading=15, textColor=colors.HexColor("#004080"), spaceBefore=12, spaceAfter=6)
    normal = styles["Normal"]
    small_gray = ParagraphStyle(name="SmallGray", fontSize=8, textColor=colors.grey)

    # Header Row
    header_table = Table([[
        RLImage(logo_path, width=30*mm, height=30*mm),
        Paragraph(f"<b>{tournament_name} Invoice</b><br/><i>Organized by Swadeshi LAN</i>", title_style),
        RLImage(qr_path, width=30*mm, height=30*mm)
    ]], colWidths=[60, 360, 60])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    player_names = ", ".join(players)
    receipt_table_data = [
        ['Receipt ID', receipt_id],
        ['Team Name', team],
        ['Players', player_names],
        ['Contact Number', contact],
        ['Amount Paid', f"{amount} INR"],
        ['Match Date & Time', match_datetime],
    ]
    receipt_table = Table(receipt_table_data, colWidths=[150, 360])
    receipt_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    elements.append(receipt_table)

    elements.append(Paragraph("Important Notes", section_heading))
    elements.append(Paragraph("""
        <ul>
        <li>Arrive 30 minutes before match time.</li>
        <li>Bring this recipt if this is a LAN tournament.</li>
        <li>Contact team Swadeshi LAN at discord if needed.</li>
        </ul>
    """, normal))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Thank you for registering. Good luck!", normal))
    elements.append(Paragraph("Support: discord.gg/SwadeshiLAN | Email: contact@swadeshilan.in", small_gray))

    doc.build(elements)
    return pdf_path

