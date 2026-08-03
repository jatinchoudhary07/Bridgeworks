import io
import logging
import zoneinfo
import datetime
from django.utils import timezone
from django.db.models import Sum
from django.core.mail import EmailMultiAlternatives
from core.models import Order, TeamMemberSettings, Batch
from core.utils.payment_utils import derive_payment_type_from_fields

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect

logger = logging.getLogger(__name__)

def get_pending_picklist_orders(org_id):
    """
    Queries all confirmed, unprinted, unfulfilled orders.
    Excludes cancelled, fulfilled, test-tagged, and 2-digit priced test orders.
    """
    # 1. Base query
    qs = Order.objects.filter(
        org_id=org_id,
        status='Confirmed',
        is_test_order=False,
        picklist_generated_at__isnull=True
    ).exclude(
        internal_fulfillment_status__in=['Fulfilled', 'Packaged', 'Manifested']
    ).exclude(
        fulfillment_status='fulfilled'
    )
    
    # 2. Exclude Shopify test tags (case-insensitive)
    qs = qs.exclude(tags__icontains='test')
    
    # 3. Exclude 2-digit test prices (total_price between 0.01 and 99.99)
    qs = qs.exclude(total_price__gt=0, total_price__lt=100)
    
    return qs

def get_payment_counts(orders_qs):
    """
    Categorizes the orders in a queryset into COD, PPCOD, and Prepaid,
    leveraging the central derive_payment_type_from_fields business logic.
    """
    cod, ppcod, prepaid = 0, 0, 0
    for order in orders_qs:
        payment_type = derive_payment_type_from_fields(
            payment_gateway_names=order.payment_gateway_names,
            financial_status=order.financial_status,
            tags=order.tags,
            raw_data=order.raw_data
        )
        if payment_type == 'COD':
            cod += 1
        elif payment_type == 'Partially Paid':
            ppcod += 1
        else:
            prepaid += 1
    return cod, ppcod, prepaid

def generate_pdf_picklist(orders_queryset) -> bytes:
    """Generates a premium, styled PDF file of aggregated SKUs matching the UI design."""
    buffer = io.BytesIO()
    
    # Resolve queryset to an unsliced query of IDs to avoid "Cannot filter a query once a slice has been taken" errors
    order_ids = list(orders_queryset.values_list('id', flat=True))
    orders_qs = Order.objects.filter(id__in=order_ids)
    
    # Page setup: A4 is 595.27 x 841.89 points
    # Usable width = 595.27 - 80 = 515.27 points
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1, # Centered
        textColor=colors.HexColor('#222222'),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=1, # Centered
        textColor=colors.HexColor('#666666'),
        spaceAfter=15
    )
    
    section_title_style = ParagraphStyle(
        'SectionTitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#FFFFFF')
    )
    
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#333333')
    )
    
    cell_bold_style = ParagraphStyle(
        'CellBoldStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#333333')
    )
    
    sku_style = ParagraphStyle(
        'SkuStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1976d2') # Blue SKU links
    )
    
    needed_style = ParagraphStyle(
        'NeededStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        alignment=1, # Centered
        textColor=colors.HexColor('#d32f2f') # Red bold quantity
    )
    
    story = []
    
    # 1. Title Block
    story.append(Paragraph("Daily Picklist - Stock Check", title_style))
    
    # Subtitle: Generated timestamp in IST (Asia/Kolkata)
    ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    ist_now = timezone.now().astimezone(ist_tz)
    time_str = ist_now.strftime('%d %b %Y, %I:%M ') + ist_now.strftime('%p').lower()
    story.append(Paragraph(f"Generated: {time_str}", subtitle_style))
    
    # 2. Section: BATCH SUMMARY
    story.append(Table(
        [[Paragraph("BATCH SUMMARY", section_title_style)]],
        colWidths=[515.27],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1976d2')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]
    ))
    story.append(Spacer(1, 4))
    
    # Group orders by batches
    batches = Batch.objects.filter(orders__in=orders_qs).distinct().order_by('-created_at')
    
    summary_data = [[
        Paragraph("Batch #", cell_bold_style),
        Paragraph("Total AWBs", cell_bold_style),
        Paragraph("COD", cell_bold_style),
        Paragraph("PPCOD", cell_bold_style),
        Paragraph("Prepaid", cell_bold_style)
    ]]
    
    total_awbs_sum = 0
    total_cod_sum = 0
    total_ppcod_sum = 0
    total_prepaid_sum = 0
    
    # Add row for each batch
    for batch in batches:
        batch_orders = orders_qs.filter(batches=batch)
        if not batch_orders.exists():
            continue
        
        awbs = batch_orders.count()
        cod, ppcod, prepaid = get_payment_counts(batch_orders)
        
        created_ist = batch.created_at.astimezone(ist_tz)
        date_suffix = f" ({created_ist.strftime('%d %b')})"
        batch_name = batch.name or f"Batch #{batch.id}"
        if date_suffix not in batch_name:
            batch_name = f"{batch_name}{date_suffix}"
            
        if len(batch_name) > 40:
            batch_name = batch_name[:37] + "..."
            
        summary_data.append([
            Paragraph(batch_name, cell_style),
            Paragraph(str(awbs), cell_style),
            Paragraph(str(cod), cell_style),
            Paragraph(str(ppcod), cell_style),
            Paragraph(str(prepaid), cell_style)
        ])
        
        total_awbs_sum += awbs
        total_cod_sum += cod
        total_ppcod_sum += ppcod
        total_prepaid_sum += prepaid
        
    # Check for unbatched orders
    unbatched_orders = orders_qs.filter(batches__isnull=True)
    if unbatched_orders.exists():
        awbs = unbatched_orders.count()
        cod, ppcod, prepaid = get_payment_counts(unbatched_orders)
        
        summary_data.append([
            Paragraph("Unbatched Orders", cell_style),
            Paragraph(str(awbs), cell_style),
            Paragraph(str(cod), cell_style),
            Paragraph(str(ppcod), cell_style),
            Paragraph(str(prepaid), cell_style)
        ])
        total_awbs_sum += awbs
        total_cod_sum += cod
        total_ppcod_sum += ppcod
        total_prepaid_sum += prepaid
        
    # Total row
    summary_data.append([
        Paragraph("TOTAL", cell_bold_style),
        Paragraph(str(total_awbs_sum), cell_bold_style),
        Paragraph(str(total_cod_sum), cell_bold_style),
        Paragraph(str(total_ppcod_sum), cell_bold_style),
        Paragraph(str(total_prepaid_sum), cell_bold_style)
    ])
    
    # Render Batch Summary Table
    batch_table = Table(summary_data, colWidths=[195.27, 80, 80, 80, 80])
    batch_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8f9fa')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'), # Left align batch names
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#eaeaea')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor('#333333')),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8f9fa')),
    ]))
    story.append(batch_table)
    story.append(Spacer(1, 20))
    
    # 3. Section: SKU Picklist
    aggregated_items = (
        orders_qs
        .values('line_items__sku', 'line_items__title')
        .annotate(totalQuantity=Sum('line_items__quantity'))
        .filter(totalQuantity__gt=0)
        .order_by('line_items__sku')
    )
    
    sku_header_text = f"SKU Picklist ({len(aggregated_items)} items)"
    story.append(Table(
        [[Paragraph(sku_header_text, section_title_style)]],
        colWidths=[515.27],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1976d2')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]
    ))
    story.append(Spacer(1, 4))
    
    sku_data = [[
        Paragraph("SKU", cell_bold_style),
        Paragraph("Product", cell_bold_style),
        Paragraph("Needed", cell_bold_style),
        Paragraph("Available", cell_bold_style)
    ]]
    
    def make_available_box():
        d = Drawing(50, 18)
        d.add(Rect(0, 0, 50, 18, rx=4, ry=4, fillColor=colors.white, strokeColor=colors.HexColor('#cccccc'), strokeWidth=1))
        return d
        
    for item in aggregated_items:
        sku = item['line_items__sku'] or 'NO-SKU'
        title = item['line_items__title'] or 'Unknown Item'
        qty = item['totalQuantity']
        
        sku_data.append([
            Paragraph(sku, sku_style),
            Paragraph(title, cell_style),
            Paragraph(str(qty), needed_style),
            make_available_box()
        ])
        
    sku_table = Table(sku_data, colWidths=[120, 235.27, 80, 80])
    sku_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8f9fa')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,0), (1,-1), 'LEFT'), # Left align SKU and Product
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#eaeaea')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(sku_table)
    
    doc.build(story)
    return buffer.getvalue()

def send_picklist_email(org_id, recipient_emails, orders_queryset, is_manual=False) -> bool:
    """
    Generates a premium PDF attachment, dynamic subject prefix matching the time of day,
    and dispatches a styled HTML email layout to recipients containing inline table summary cards.
    """
    if not orders_queryset.exists():
        logger.info(f"[PICKLIST] No orders to export for org {org_id}. Skipping email.")
        return False
        
    if not recipient_emails:
        logger.warning(f"[PICKLIST] No recipient emails provided for org {org_id}.")
        return False

    # Resolve queryset to an unsliced query of IDs to avoid "Cannot filter a query once a slice has been taken" errors
    order_ids = list(orders_queryset.values_list('id', flat=True))
    orders_qs = Order.objects.filter(id__in=order_ids)

    # 1. Determine dynamic subject prefix based on IST execution hour
    ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    ist_now = timezone.now().astimezone(ist_tz)
    hour = ist_now.hour
    
    if 5 <= hour < 12:
        prefix = "Morning"
    elif 12 <= hour < 17:
        prefix = "Afternoon"
    elif 17 <= hour < 22:
        prefix = "Evening"
    else:
        prefix = "Night"
        
    date_str = ist_now.strftime('%d %b %Y')
    subject = f"📦 {prefix} Picklist - {date_str}" if not is_manual else f"📦 Picklist Export - {date_str} (Manual)"

    # 2. Generate PDF bytes
    pdf_bytes = generate_pdf_picklist(orders_qs)

    # 3. Generate HTML Table Rows dynamically for the email body
    batches = Batch.objects.filter(orders__in=orders_qs).distinct().order_by('-created_at')
    
    table_rows_html = ""
    total_awbs_sum = 0
    total_cod_sum = 0
    total_ppcod_sum = 0
    total_prepaid_sum = 0
    
    for batch in batches:
        batch_orders = orders_qs.filter(batches=batch)
        if not batch_orders.exists():
            continue
        
        awbs = batch_orders.count()
        cod, ppcod, prepaid = get_payment_counts(batch_orders)
        
        created_ist = batch.created_at.astimezone(ist_tz)
        date_suffix = f" ({created_ist.strftime('%d %b')})"
        batch_name = batch.name or f"Batch #{batch.id}"
        if date_suffix not in batch_name:
            batch_name = f"{batch_name}{date_suffix}"
            
        if len(batch_name) > 40:
            batch_name = batch_name[:37] + "..."
            
        table_rows_html += f"""
        <tr>
            <td style="text-align: left; padding: 12px 10px; border-bottom: 1px solid #eaeaea; font-weight: 500; color: #333333;">{batch_name}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eaeaea; color: #333333;">{awbs}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eaeaea; color: #333333;">{cod}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eaeaea; color: #333333;">{ppcod}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eaeaea; color: #333333;">{prepaid}</td>
        </tr>
        """
        total_awbs_sum += awbs
        total_cod_sum += cod
        total_ppcod_sum += ppcod
        total_prepaid_sum += prepaid
        
    unbatched_orders = orders_qs.filter(batches__isnull=True)
    if unbatched_orders.exists():
        awbs = unbatched_orders.count()
        cod, ppcod, prepaid = get_payment_counts(unbatched_orders)
        
        table_rows_html += f"""
        <tr>
            <td style="text-align: left; padding: 12px 10px; border-bottom: 1px solid #eaeaea; font-weight: 500; color: #333333;">Unbatched Orders</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eaeaea; color: #333333;">{awbs}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eaeaea; color: #333333;">{cod}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eaeaea; color: #333333;">{ppcod}</td>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eaeaea; color: #333333;">{prepaid}</td>
        </tr>
        """
        total_awbs_sum += awbs
        total_cod_sum += cod
        total_ppcod_sum += ppcod
        total_prepaid_sum += prepaid
        
    table_rows_html += f"""
    <tr style="background-color: #f8f9fa; font-weight: bold; border-top: 2px solid #1976d2 !important;">
        <td style="text-align: left; padding: 12px 10px; font-weight: bold; color: #111111;">TOTAL</td>
        <td style="padding: 12px 10px; font-weight: bold; color: #111111;">{total_awbs_sum}</td>
        <td style="padding: 12px 10px; font-weight: bold; color: #111111;">{total_cod_sum}</td>
        <td style="padding: 12px 10px; font-weight: bold; color: #111111;">{total_ppcod_sum}</td>
        <td style="padding: 12px 10px; font-weight: bold; color: #111111;">{total_prepaid_sum}</td>
    </tr>
    """

    # 4. Compile HTML body content matching the Shipway layout design
    html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #333333;
            background-color: #f4f5f7;
            margin: 0;
            padding: 0;
            -webkit-font-smoothing: antialiased;
        }}
        .wrapper {{
            background-color: #f4f5f7;
            padding: 20px 10px;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border: 1px solid #e1e4e8;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        .header {{
            padding: 25px 20px;
            text-align: center;
            background-color: #ffffff;
            border-bottom: 1px solid #f0f1f3;
        }}
        .logo {{
            font-size: 26px;
            font-weight: 900;
            color: #1976d2;
            letter-spacing: -1px;
            text-decoration: none;
        }}
        .content {{
            padding: 30px 40px;
        }}
        .salutation {{
            font-size: 16px;
            font-weight: bold;
            color: #222222;
            margin-bottom: 15px;
        }}
        .intro {{
            font-size: 14px;
            line-height: 1.5;
            color: #555555;
            margin-bottom: 25px;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: bold;
            color: #111111;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .table-container {{
            margin-bottom: 25px;
            border: 1px solid #eaeaea;
            border-radius: 6px;
            overflow: hidden;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
            color: #555555;
            text-align: center;
            padding: 12px 10px;
            border-bottom: 1px solid #eaeaea;
        }}
        th:first-child {{
            text-align: left;
        }}
        .btn-container {{
            text-align: center;
            margin: 30px 0 10px 0;
        }}
        .btn {{
            display: inline-block;
            background-color: #1976d2;
            color: #ffffff !important;
            text-decoration: none;
            padding: 12px 35px;
            font-size: 14px;
            font-weight: bold;
            border-radius: 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .footer {{
            background-color: #ffffff;
            padding: 20px 40px 30px 40px;
            border-top: 1px solid #f0f1f3;
            font-size: 13px;
            color: #666666;
            line-height: 1.5;
        }}
        .signature {{
            font-weight: bold;
            color: #333333;
            margin-bottom: 4px;
        }}
        .footer-note {{
            font-size: 11px;
            color: #999999;
            margin-top: 25px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="container">
            <div class="header">
                <span class="logo">Shori Workspace</span>
            </div>
            <div class="content">
                <div class="salutation">Hello Team,</div>
                <div class="intro">
                    Below is the scheduled daily report of orders that are ready to pack and need your attention.
                    The high-fidelity PDF picklist is attached to this email.
                </div>
                
                <div class="section-title">Batch Summary</div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th style="text-align: left;">Batch #</th>
                                <th>Total AWBs</th>
                                <th>COD</th>
                                <th>PPCOD</th>
                                <th>Prepaid</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                        </tbody>
                    </table>
                </div>
                
                <div class="btn-container">
                    <a href="http://localhost:5173/operations/morning-report" class="btn">View on Dashboard</a>
                </div>
            </div>
            <div class="footer">
                <div class="signature">Best regards,</div>
                <div>Shori Automation</div>
                <div class="footer-note">
                    Automatically generated by Shori Workspace.<br>
                    Please do not reply to this email.
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

    # 5. Compile plain-text backup body
    export_type_str = f"Scheduled {prefix} Report ({ist_now.strftime('%I:%M %p')})" if not is_manual else "Manual Export Request"
    text_body = (
        f"Hello Team,\n\n"
        f"Please find attached the daily picklist PDF report containing the SKUs of the confirmed orders for {date_str}.\n\n"
        f"- Total Orders: {orders_qs.count()}\n"
        f"- Export Type: {export_type_str}\n\n"
        f"Best regards,\nShori Automation"
    )

    # 6. Build and dispatch multi-alternatives email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=None,  # Use DEFAULT_FROM_EMAIL
        to=recipient_emails
    )
    email.attach_alternative(html_body, "text/html")
    
    email.attach(
        filename=f"picklist_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        content=pdf_bytes,
        mimetype="application/pdf"
    )
    
    email.send()
    
    # Mark orders as exported to prevent duplication
    Order.objects.filter(id__in=order_ids).update(picklist_generated_at=timezone.now())
    logger.info(f"[PICKLIST] Successfully sent email to {recipient_emails} and updated {len(order_ids)} orders.")
    return True
