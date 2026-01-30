from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime


def generate_prescription_pdf(prescription_data):
    """
    Generate a PDF prescription with SolaceSquad letterhead
    
    Args:
        prescription_data: Dictionary containing prescription details
        
    Returns:
        BytesIO object containing the PDF
    """
    buffer = BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0284c7'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#374151'),
        spaceAfter=6
    )
    
    # Add letterhead
    elements.append(Paragraph("SolaceSquad", title_style))
    elements.append(Paragraph("Your Wellbeing Partner", subtitle_style))
    
    # Add horizontal line
    elements.append(Spacer(1, 0.1*inch))
    line_data = [['', '']]
    line_table = Table(line_data, colWidths=[6.5*inch])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#0284c7')),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Prescription header info
    header_data = [
        ['Prescription Number:', f"Rx #{prescription_data['id']}", 
         'Date:', prescription_data['created_at'].strftime('%B %d, %Y')]
    ]
    header_table = Table(header_data, colWidths=[1.5*inch, 1.75*inch, 0.75*inch, 1.5*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Consultant information
    elements.append(Paragraph("Prescribed By", heading_style))
    consultant_info = f"""
    <b>Dr. {prescription_data['consultant_name']}</b><br/>
    {prescription_data['consultant_specialization']}<br/>
    """
    elements.append(Paragraph(consultant_info, normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Patient information
    elements.append(Paragraph("Patient Name", heading_style))
    elements.append(Paragraph(prescription_data['patient_name'], normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Diagnosis
    if prescription_data.get('diagnosis'):
        elements.append(Paragraph("Diagnosis", heading_style))
        elements.append(Paragraph(prescription_data['diagnosis'], normal_style))
        elements.append(Spacer(1, 0.2*inch))
    
    # Medications
    elements.append(Paragraph("Medications", heading_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Create medications table
    med_data = [['#', 'Medication', 'Dosage', 'Frequency', 'Duration']]
    
    for idx, item in enumerate(prescription_data['items'], 1):
        med_data.append([
            str(idx),
            item['medication_name'],
            item.get('dosage', '-'),
            item.get('frequency', '-'),
            item.get('duration', '-')
        ])
    
    med_table = Table(med_data, colWidths=[0.4*inch, 2.2*inch, 1.2*inch, 1.2*inch, 1.0*inch])
    med_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0284c7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#374151')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
    ]))
    elements.append(med_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Instructions for each medication
    for idx, item in enumerate(prescription_data['items'], 1):
        if item.get('instructions'):
            instr_text = f"<b>{idx}. {item['medication_name']}:</b> {item['instructions']}"
            elements.append(Paragraph(instr_text, normal_style))
    
    if any(item.get('instructions') for item in prescription_data['items']):
        elements.append(Spacer(1, 0.2*inch))
    
    # Additional notes
    if prescription_data.get('notes'):
        elements.append(Paragraph("Additional Notes", heading_style))
        elements.append(Paragraph(prescription_data['notes'], normal_style))
        elements.append(Spacer(1, 0.3*inch))
    
    # Footer
    elements.append(Spacer(1, 0.3*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=4
    )
    
    elements.append(Paragraph(
        "<b>Note:</b> This is a digital prescription. Please follow the prescribed medication as directed.",
        footer_style
    ))
    elements.append(Paragraph(
        "For any queries, please contact your healthcare provider.",
        footer_style
    ))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf
