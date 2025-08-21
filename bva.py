import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO, StringIO
import json
import csv
from datetime import datetime

# --- PDF REPORTING DEPENDENCIES (Optional) ---
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import matplotlib.pyplot as plt
    REPORT_DEPENDENCIES_AVAILABLE = True
except ImportError:
    REPORT_DEPENDENCIES_AVAILABLE = False


# --- CONFIGURATION & REPORTING FUNCTIONS ---

def get_all_input_values():
    """Gathers all user-configurable inputs from the Streamlit session state."""
    input_values = {}
    eval_years = st.session_state.get('eval_years', 3)

    # List of all keys used for st widgets
    keys = [
        'eval_years', 'discount_rate', 'fte_annual_cost', 'annual_working_hours',
        'selected_currency_name', 'implementation_delay_months', 'ramp_up_months',
        'billing_start_month', 'manage_aiops_fte', 'avg_revenue_per_customer',
        'aiops_revenue_contribution_pct', 'services_cost', 'annual_alerts_per_customer',
        'base_customers', 'alert_reduction_pct', 'alert_triage_time_min',
        'triage_time_reduction_pct', 'annual_incidents_per_customer',
        'incident_reduction_pct', 'incident_handling_time_min',
        'incident_time_reduction_pct', 'annual_major_incidents',
        'avg_major_incident_cost_per_hour', 'avg_mttr_hours', 'mttr_improvement_pct',
        'fte_alerts_pct', 'fte_incidents_pct', 'fte_total', 'confidence_level' # Added confidence_level
    ]

    for key in keys:
        if key in st.session_state:
            input_values[key] = st.session_state[key]

    # Handle list-based inputs from dynamically created keys
    input_values['fte_pattern'] = [st.session_state.get(f"fte_pattern_year_{i}", 0) for i in range(eval_years)]
    input_values['customer_growth_per_year'] = [st.session_state.get(f"customer_growth_year_{i}", 0) for i in range(eval_years)]
    input_values['tool_savings_per_year'] = [st.session_state.get(f"tool_savings_year_{i}", 0.0) for i in range(eval_years)]
    input_values['platform_costs'] = [st.session_state.get(f"platform_costs_year_{i}", 0.0) for i in range(eval_years)]

    return input_values

def export_to_json(input_values):
    """Exports input values to a JSON string."""
    export_data = {
        'metadata': {
            'export_date': datetime.now().isoformat(),
            'version': '3.6-confidence-display',
            'tool': 'AIOPs Business Value Assessment Modelling Tool'
        },
        'configuration': input_values
    }
    return json.dumps(export_data, indent=2)

def export_to_csv(input_values):
    """Exports input values to a CSV string, handling lists."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Parameter', 'Value'])

    for key, value in input_values.items():
        if isinstance(value, list):
            # Flatten lists into multiple rows
            for i, item in enumerate(value):
                writer.writerow([f"{key}_{i+1}", item])
        else:
            writer.writerow([key, value])

    return output.getvalue()

def import_from_json(json_content):
    """Imports configuration from JSON and updates session state."""
    try:
        data = json.loads(json_content)
        config = data.get('configuration', data) # Handle both formats
        for key, value in config.items():
            st.session_state[key] = value
        return True, f"✅ Successfully imported {len(config)} parameters from JSON."
    except Exception as e:
        return False, f"❌ Error importing JSON: {e}"


def import_from_csv(csv_content):
    """Imports configuration from CSV and updates session state."""
    try:
        reader = csv.reader(StringIO(csv_content))
        next(reader)  # Skip header
        
        list_items = {}
        count = 0

        for row in reader:
            key, value = row
            # Try converting to a number
            try:
                if '.' in value: value = float(value)
                else: value = int(value)
            except (ValueError, TypeError):
                pass
            
            # Check for flattened list items (e.g., "fte_pattern_1")
            if '_' in key and key.rsplit('_', 1)[-1].isdigit():
                base_key, index = key.rsplit('_', 1)
                if base_key not in list_items:
                    list_items[base_key] = []
                # Store as tuple (index, value) for later sorting
                list_items[base_key].append((int(index), value))
            else:
                st.session_state[key] = value
                count += 1
        
        # Handle the reconstructed lists
        for base_key, items in list_items.items():
            items.sort() # Sort by index (e.g., _1, _2, _3)
            sorted_values = [v for i, v in items]
            st.session_state[base_key] = sorted_values
            count += len(sorted_values)

        return True, f"✅ Successfully imported {count} parameters from CSV."
    except Exception as e:
        return False, f"❌ Error importing CSV: {e}"


def generate_pdf_report(logo_file=None):
    """Generates a comprehensive PDF executive summary report."""
    if not REPORT_DEPENDENCIES_AVAILABLE:
        return None, "PDF generation requires reportlab and matplotlib. Please install them."

    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        elements = []

        # --- Get data from session state ---
        currency_symbol = st.session_state.get('currency_symbol', '$')
        eval_years = st.session_state.get('eval_years', 3)
        confidence_level = st.session_state.get('confidence_level', 'Realistic') # Get confidence level
        total_investment = sum(st.session_state.get('costs_per_year', []))
        total_benefits = sum(st.session_state.get('total_benefits_per_year', []))
        net_value = st.session_state.get('net_value', 0)
        roi = st.session_state.get('roi', 0)
        payback_period = st.session_state.get('payback_period', '> term')
        recommendation = st.session_state.get('recommendation', 'N/A')
        summary_message = st.session_state.get('summary_message', '')
        df_data = st.session_state.get('df_data', pd.DataFrame())
        
        # New: Get business value stories
        cio_story = st.session_state.get('cio_story', '')
        cfo_story = st.session_state.get('cfo_story', '')
        head_of_support_story = st.session_state.get('head_of_support_story', '')


        # --- Styles ---
        title_style = ParagraphStyle('CustomTitle', parent=styles['h1'], fontSize=22, textColor=colors.HexColor("#003366"), spaceAfter=20, alignment=TA_CENTER)
        heading_style = ParagraphStyle('CustomHeading', parent=styles['h2'], fontSize=16, textColor=colors.HexColor("#003366"), spaceBefore=12, spaceAfter=8)
        body_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontSize=10, spaceAfter=10, alignment=TA_LEFT, leading=14)
        story_heading_style = ParagraphStyle('StoryHeading', parent=styles['h3'], fontSize=14, textColor=colors.HexColor("#0056b3"), spaceBefore=10, spaceAfter=5)


        # --- Logo ---
        if logo_file:
            logo_file.seek(0)
            logo_image = Image(logo_file, width=2*inch, height=1*inch)
            logo_image.hAlign = 'CENTER'
            elements.append(logo_image)
            elements.append(Spacer(1, 20))

        # --- Title ---
        elements.append(Paragraph(f"Business Value Assessment Report ({confidence_level} Scenario)", title_style)) # Add confidence to title
        elements.append(Spacer(1, 30))

        # --- Executive Summary ---
        elements.append(Paragraph("Executive Summary", heading_style))
        summary_text = f"""
        This assessment analyzes the financial impact of the AIOps Platform investment over a {eval_years}-year period, based on a <b>{confidence_level}</b> confidence scenario.
        The analysis indicates a <b>{recommendation}</b>. {summary_message}<br/><br/>
        The project is projected to deliver a Net Present Value (NPV) of <b>{currency_symbol}{net_value:,.0f}</b>,
        an ROI of <b>{roi:.1f}%</b>, with a payback period of <b>{payback_period} months</b>.
        The total investment is estimated at {currency_symbol}{total_investment:,.0f}, generating total benefits
        of {currency_symbol}{total_benefits:,.0f}.
        """
        elements.append(Paragraph(summary_text, body_style))
        elements.append(Spacer(1, 20))


        # --- Key Metrics Table ---
        elements.append(Paragraph("Key Financial Metrics", heading_style))
        metrics_data = [
            ['Metric', 'Value'],
            ['Net Present Value (NPV)', f'{currency_symbol}{net_value:,.0f}'],
            ['Return on Investment (ROI)', f'{roi:.1f}%'],
            ['Payback Period', f'{payback_period} months'],
            ['Total Benefits', f'{currency_symbol}{total_benefits:,.0f}'],
            ['Total Investment', f'{currency_symbol}{total_investment:,.0f}'],
            ['Confidence Level', f'{confidence_level}'], # Add confidence level to table
        ]
        metrics_table = Table(metrics_data, colWidths=[3*inch, 2*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F0F8FF")),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(metrics_table)
        elements.append(PageBreak())


        # --- Yearly Breakdown Table ---
        elements.append(Paragraph("Yearly Financial Breakdown", heading_style))

        # Convert dataframe to list of lists for ReportLab table
        table_data = [df_data.columns.tolist()] + df_data.values.tolist()
        yearly_table = Table(table_data, hAlign='LEFT', repeatRows=1)
        yearly_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F0F8FF")),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(yearly_table)
        elements.append(Spacer(1, 20))

        # --- Business Value Stories for PDF ---
        elements.append(Paragraph("Business Value Stories", heading_style))
        elements.append(Paragraph("For the CIO", story_heading_style))
        elements.append(Paragraph(cio_story, body_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("For the CFO", story_heading_style))
        elements.append(Paragraph(cfo_story, body_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("For the Head of Support", story_heading_style))
        elements.append(Paragraph(head_of_support_story, body_style))
        elements.append(Spacer(1, 20))


        # --- Footer ---
        footer_text = f"Report generated on {datetime.now().strftime('%B %d, %Y')}"
        elements.append(Paragraph(footer_text, styles['Italic']))

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data, None

    except Exception as e:
        return None, f"Error generating PDF: {e}"


# --- APP CONFIGURATION ---
st.set_page_config(page_title="AIOPs BVA Modelling Tool", layout="wide")

# --- INITIALIZE SESSION STATE DEFAULTS ---
if 'eval_years' not in st.session_state:
    st.session_state['eval_years'] = 3
if 'discount_rate' not in st.session_state:
    st.session_state['discount_rate'] = 3
if 'fte_annual_cost' not in st.session_state:
    st.session_state['fte_annual_cost'] = 0.0
if 'annual_working_hours' not in st.session_state:
    st.session_state['annual_working_hours'] = 1900
if 'selected_currency_name' not in st.session_state:
    st.session_state['selected_currency_name'] = "US Dollar ($)"
if 'currency_symbol' not in st.session_state:
    st.session_state['currency_symbol'] = "$"
if 'confidence_level' not in st.session_state:
    st.session_state['confidence_level'] = 'Realistic'
if 'implementation_delay_months' not in st.session_state:
    st.session_state['implementation_delay_months'] = 4
if 'ramp_up_months' not in st.session_state:
    st.session_state['ramp_up_months'] = 3
if 'billing_start_month' not in st.session_state:
    st.session_state['billing_start_month'] = 4
if 'manage_aiops_fte' not in st.session_state:
    st.session_state['manage_aiops_fte'] = 0.0
if 'avg_revenue_per_customer' not in st.session_state:
    st.session_state['avg_revenue_per_customer'] = 0.0
if 'aiops_revenue_contribution_pct' not in st.session_state:
    st.session_state['aiops_revenue_contribution_pct'] = 0
if 'services_cost' not in st.session_state:
    st.session_state['services_cost'] = 0.0
if 'annual_alerts_per_customer' not in st.session_state:
    st.session_state['annual_alerts_per_customer'] = 0
if 'base_customers' not in st.session_state:
    st.session_state['base_customers'] = 1
if 'alert_reduction_pct' not in st.session_state:
    st.session_state['alert_reduction_pct'] = 0
if 'alert_triage_time_min' not in st.session_state:
    st.session_state['alert_triage_time_min'] = 0
if 'triage_time_reduction_pct' not in st.session_state:
    st.session_state['triage_time_reduction_pct'] = 0
if 'annual_incidents_per_customer' not in st.session_state:
    st.session_state['annual_incidents_per_customer'] = 0
if 'incident_reduction_pct' not in st.session_state:
    st.session_state['incident_reduction_pct'] = 0
if 'incident_handling_time_min' not in st.session_state:
    st.session_state['incident_handling_time_min'] = 0
if 'incident_time_reduction_pct' not in st.session_state:
    st.session_state['incident_time_reduction_pct'] = 0
if 'annual_major_incidents' not in st.session_state:
    st.session_state['annual_major_incidents'] = 0
if 'avg_major_incident_cost_per_hour' not in st.session_state:
    st.session_state['avg_major_incident_cost_per_hour'] = 0.0
if 'avg_mttr_hours' not in st.session_state:
    st.session_state['avg_mttr_hours'] = 0.0
if 'mttr_improvement_pct' not in st.session_state:
    st.session_state['mttr_improvement_pct'] = 0
if 'fte_alerts_pct' not in st.session_state:
    st.session_state['fte_alerts_pct'] = 0
if 'fte_incidents_pct' not in st.session_state:
    st.session_state['fte_incidents_pct'] = 0
if 'fte_total' not in st.session_state:
    st.session_state['fte_total'] = 1
if 'fte_pattern' not in st.session_state:
    st.session_state['fte_pattern'] = [0, 0, 0, 0, 0] # For up to 5 years
if 'customer_growth_per_year' not in st.session_state:
    st.session_state['customer_growth_per_year'] = [0] * 5 # For up to 5 years
if 'tool_savings_per_year' not in st.session_state:
    st.session_state['tool_savings_per_year'] = [0.0] * 5 # For up to 5 years
if 'platform_costs' not in st.session_state:
    st.session_state['platform_costs'] = [0.0] * 5 # For up to 5 years
if 'cio_story' not in st.session_state:
    st.session_state['cio_story'] = ""
if 'cfo_story' not in st.session_state:
    st.session_state['cfo_story'] = ""
if 'head_of_support_story' not in st.session_state:
    st.session_state['head_of_support_story'] = ""


# --- SIDEBAR IMPORT CONFIGURATION (Moved to the very top of app logic) ---
with st.sidebar:
    st.header("📑 Reports & Configuration")
    
    uploaded_config = st.file_uploader("Import Configuration File", type=['json', 'csv'])
    apply_config = st.button("Apply Imported Configuration")

    if apply_config:
        if uploaded_config is not None:
            try:
                content = uploaded_config.read().decode('utf-8')
                if uploaded_config.name.endswith('.json'):
                    success, message = import_from_json(content)
                else:
                    success, message = import_from_csv(content)

                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            except Exception as e:
                st.error(f"An error occurred while processing the file: {e}")
        else:
            st.warning("Please upload a configuration file first.")

    st.markdown("---")


# --- MAIN TITLE ---
st.title("📊 AIOPs Business Value Assessment Modelling Tool")


# --- SIDEBAR INPUT PARAMETERS ---
with st.sidebar:
    st.header("⚙️ Input Parameters")

    # --- 📅 Evaluation Settings ---
    st.markdown("#### 📅 Evaluation Settings")
    
    confidence_level = st.selectbox(
        "Confidence Level",
        ['Conservative', 'Realistic', 'Optimistic'],
        index=1,
        key='confidence_level',
        help="Adjusts key benefit drivers. 'Realistic' uses your exact inputs. 'Conservative' is more cautious, 'Optimistic' is more aggressive."
    )

    # --- NEW: Moved multiplier logic into the sidebar and added a display box ---
    confidence_multipliers = {
        'Conservative': {'benefits': 0.8, 'timing': 1.25},
        'Realistic':    {'benefits': 1.0, 'timing': 1.0},
        'Optimistic':   {'benefits': 1.2, 'timing': 0.8}
    }
    benefit_multiplier = confidence_multipliers[st.session_state['confidence_level']]['benefits']
    timing_multiplier = confidence_multipliers[st.session_state['confidence_level']]['timing']

    st.markdown(f"""
    <div style="background-color:#F0F2F6; padding: 10px; border-radius: 5px; margin-bottom: 10px; margin-top: 10px;">
    <small>Active Scenario Multipliers:</small><br>
    <strong>Benefit Multiplier:</strong> <code>{benefit_multiplier:.2f}x</code><br>
    <strong>Timing Multiplier:</strong> <code>{timing_multiplier:.2f}x</code>
    </div>
    """, unsafe_allow_html=True)
    # --- END OF NEW CODE ---

    eval_years_index = [1, 3, 5].index(st.session_state['eval_years'])
    eval_years = st.selectbox("Evaluation Period (years)", [1, 3, 5], index=eval_years_index, key='eval_years')

    discount_rate = st.slider("NPV Discount Rate (%)", 0, 20, st.session_state['discount_rate'], key='discount_rate')
    fte_annual_cost = st.number_input("Average Annual Cost per FTE", 0.0, value=st.session_state['fte_annual_cost'], key='fte_annual_cost')
    annual_working_hours = st.number_input("Annual Working Hours per FTE", 0, value=st.session_state['annual_working_hours'], key='annual_working_hours')

    # Currency Selector
    currency_options = {
        "US Dollar ($)": "$", "Euro (€)": "€", "British Pound (£)": "£", "Japanese Yen (¥)": "¥",
        "Canadian Dollar (C$)": "C$", "Czech Koruna (CZK)": "CZK", "Australian Dollar (A$)": "A$",
        "Swiss Franc (CHF)": "CHF ", "Chinese Yuan (¥)": "¥", "Indian Rupee (₹)": "₹"
    }
    currency_keys = list(currency_options.keys())
    currency_index = currency_keys.index(st.session_state['selected_currency_name'])
    selected_currency_name = st.selectbox("Select Currency", currency_keys, index=currency_index, key='selected_currency_name')
    currency_symbol = currency_options[selected_currency_name]
    st.session_state['currency_symbol'] = currency_symbol


    # --- 🛠️ Project Timing ---
    st.markdown("#### 🛠️ Project Timing")
    implementation_delay_months = st.slider("Implementation Delay (months)", 0, 24, st.session_state['implementation_delay_months'], key='implementation_delay_months')
    ramp_up_months = st.slider("Benefits Ramp-up Period (months)", 0, 24, st.session_state['ramp_up_months'], key='ramp_up_months')
    billing_start_month = st.slider("Billing Start Month", 1, 24, st.session_state['billing_start_month'], key='billing_start_month')

    # --- ⚙️ AIOps Platform Management FTEs ---
    st.markdown("#### ⚙️ AIOps Platform Management FTEs")
    manage_aiops_fte = st.number_input("FTEs Dedicated to AIOps Platform Management", 0.0, value=st.session_state['manage_aiops_fte'], step=0.1, key='manage_aiops_fte')

    # --- 👥 FTE & Revenue ---
    st.markdown("#### 👥 FTE & Revenue")
    fte_pattern = [st.number_input(f"FTEs Avoided in Year {i+1}", 0, value=st.session_state['fte_pattern'][i] if i < len(st.session_state['fte_pattern']) else 0, key=f"fte_pattern_year_{i}") for i in range(eval_years)]
    avg_revenue_per_customer = st.number_input("Average Revenue Per Customer", 0.0, value=st.session_state['avg_revenue_per_customer'], key='avg_revenue_per_customer')
    customer_growth_per_year = [st.number_input(f"Customer Growth in Year {i+1}", 0, value=st.session_state['customer_growth_per_year'][i] if i < len(st.session_state['customer_growth_per_year']) else 0, key=f"customer_growth_year_{i}") for i in range(eval_years)]
    aiops_revenue_contribution_pct = st.slider("% of Revenue Contribution Attributed to New AIOps Platform", 0, 100, st.session_state['aiops_revenue_contribution_pct'], key='aiops_revenue_contribution_pct')

    # --- 💰 Tool Savings & Platform Investment Costs ---
    st.markdown("#### 💰 Tool Savings & New Platform Investment Costs")
    tool_savings_per_year = [st.number_input(f"Tool Savings in Year {i+1}", 0.0, value=st.session_state['tool_savings_per_year'][i] if i < len(st.session_state['tool_savings_per_year']) else 0.0, key=f"tool_savings_year_{i}") for i in range(eval_years)]
    platform_costs = [st.number_input(f"Platform Cost in Year {i+1}", 0.0, value=st.session_state['platform_costs'][i] if i < len(st.session_state['platform_costs']) else 0.0, key=f"platform_costs_year_{i}") for i in range(eval_years)]
    services_cost = st.number_input("One-time Services Cost (Year 1 only)", 0.0, value=st.session_state['services_cost'], key='services_cost')

    # --- 🔔 Alerts & Incidents ---
    st.markdown("#### 🔔 Alerts & Incidents")
    st.markdown("##### 📈 Alert Volume")
    annual_alerts_per_customer = st.number_input("Average Annual Alert Volume by Customer", 0, value=st.session_state['annual_alerts_per_customer'], key='annual_alerts_per_customer')
    base_customers = st.number_input("Base Number of Customers", 0, value=st.session_state['base_customers'], key='base_customers')
    alert_reduction_pct = st.slider("Alert Reduction with AIOps (%)", 0, 100, st.session_state['alert_reduction_pct'], key='alert_reduction_pct')
    alert_triage_time_min = st.number_input("Triage Time per Alert (min)", 0, value=st.session_state['alert_triage_time_min'], key='alert_triage_time_min')
    triage_time_reduction_pct = st.slider("Triage Time Reduction (%)", 0, 100, st.session_state['triage_time_reduction_pct'], key='triage_time_reduction_pct')

    st.markdown("##### 🧯 Incident Volume")
    annual_incidents_per_customer = st.number_input("Average Annual Incident Volume by Customer", 0, value=st.session_state['annual_incidents_per_customer'], key='annual_incidents_per_customer')
    incident_reduction_pct = st.slider("Incident Reduction with AIOps (%)", 0, 100, st.session_state['incident_reduction_pct'], key='incident_reduction_pct')
    incident_handling_time_min = st.number_input("Handling Time per Incident (min)", 0, value=st.session_state['incident_handling_time_min'], key='incident_handling_time_min')
    incident_time_reduction_pct = st.slider("Incident Time Reduction (%)", 0, 100, st.session_state['incident_time_reduction_pct'], key='incident_time_reduction_pct')

    st.markdown("##### 🚨 Major Incidents")
    annual_major_incidents = st.number_input("Total Infrastructure Related Major Incidents per Year (P1)", 0, value=st.session_state['annual_major_incidents'], key='annual_major_incidents')
    avg_major_incident_cost_per_hour = st.number_input("Average Major Incident Cost per Hour", 0.0, value=st.session_state['avg_major_incident_cost_per_hour'], key='avg_major_incident_cost_per_hour')
    avg_mttr_hours = st.number_input("Average MTTR (hours)", 0.0, value=st.session_state['avg_mttr_hours'], key='avg_mttr_hours')
    mttr_improvement_pct = st.slider("MTTR Improvement Percentage", 0, 100, st.session_state['mttr_improvement_pct'], key='mttr_improvement_pct')

    st.markdown("##### 👷 FTE Time Allocation")
    fte_alerts_pct = st.slider("Percent of FTE Time on Alerts (%)", 0, 100, st.session_state['fte_alerts_pct'], key='fte_alerts_pct')
    fte_incidents_pct = st.slider("Percent of FTE Time on Incidents (%)", 0, 100, st.session_state['fte_incidents_pct'], key='fte_incidents_pct')
    fte_total = st.number_input("Total FTEs in Ops", 1, value=st.session_state['fte_total'], key='fte_total')


    # --- PDF REPORTING & EXPORT/IMPORT UI (Now after config import) ---
    st.markdown("---")
    st.header("📊 Reports & Data")

    with st.expander("🖼️ Upload Company Logo for PDF"):
        uploaded_logo = st.file_uploader("Choose logo file", type=['png', 'jpg', 'jpeg'], key="pdf_logo_uploader")
        if uploaded_logo:
            st.image(uploaded_logo, width=200)

    with st.expander("📄 Generate PDF Executive Summary"):
        if st.button("Generate PDF Report"):
            if not REPORT_DEPENDENCIES_AVAILABLE:
                st.error("PDF dependencies not found. Please install reportlab and matplotlib.")
            else:
                with st.spinner("Generating PDF..."):
                    pdf_data, error = generate_pdf_report(uploaded_logo)
                    if error:
                        st.error(f"Error: {error}")
                    else:
                        st.download_button(
                            label="📥 Download PDF Report",
                            data=pdf_data,
                            file_name=f"BVA_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )

    with st.expander("🔄 Export Configuration"):
        export_format = st.selectbox("Export Format", ["JSON", "CSV"], key="export_format_selector")
        if st.button("Export Configuration"):
            inputs = get_all_input_values()
            if export_format == "JSON":
                data = export_to_json(inputs)
                mime = "application/json"
                fn = f"bva_config_{datetime.now().strftime('%Y%m%d')}.json"
            else:
                data = export_to_csv(inputs)
                mime = "text/csv"
                fn = f"bva_config_{datetime.now().strftime('%Y%m%d')}.csv"

            st.download_button(f"Download {export_format}", data, file_name=fn, mime=mime)


# --- CONFIDENCE LEVEL ADJUSTMENT LOGIC ---
# This block uses the multipliers calculated in the sidebar
# Create 'adjusted' variables to use in calculations.
# This keeps the original session_state values intact on the sliders.
adj_ramp_up_months = st.session_state['ramp_up_months'] * timing_multiplier
adj_alert_reduction_pct = min(100, st.session_state['alert_reduction_pct'] * benefit_multiplier)
adj_triage_time_reduction_pct = min(100, st.session_state['triage_time_reduction_pct'] * benefit_multiplier)
adj_incident_reduction_pct = min(100, st.session_state['incident_reduction_pct'] * benefit_multiplier)
adj_incident_time_reduction_pct = min(100, st.session_state['incident_time_reduction_pct'] * benefit_multiplier)
adj_mttr_improvement_pct = min(100, st.session_state['mttr_improvement_pct'] * benefit_multiplier)
adj_aiops_revenue_contribution_pct = min(100, st.session_state['aiops_revenue_contribution_pct'] * benefit_multiplier)

# Adjust list-based variables
adj_fte_pattern = [val * benefit_multiplier for val in st.session_state['fte_pattern']]
adj_tool_savings_per_year = [val * benefit_multiplier for val in st.session_state['tool_savings_per_year']]


# --- MAIN CALCULATIONS ---
# MODIFIED: All calculations now use the 'adj_' prefixed variables
hourly_fte_cost = st.session_state['fte_annual_cost'] / st.session_state['annual_working_hours']

# Total customers per year
total_customers_in_year = []
current_customer_count = st.session_state['base_customers']
for i in range(eval_years):
    current_customer_count += st.session_state[f'customer_growth_year_{i}']
    total_customers_in_year.append(current_customer_count)

projected_alerts = [total_customers_in_year[i] * st.session_state['annual_alerts_per_customer'] for i in range(eval_years)]
projected_incidents = [total_customers_in_year[i] * st.session_state['annual_incidents_per_customer'] for i in range(eval_years)]

# Initialize lists
people_efficiency_per_year = []
ftee_avoidance_per_year = []
aiops_revenue_growth_per_year = []
tool_savings_annual = []
hard_savings_per_year = []
soft_savings_per_year = []
total_benefits_per_year = []
costs_per_year = []
discounted_benefits = []
discounted_costs = []
npv_per_year = []
major_incident_savings_per_year = []
discounted_hard_savings = []
discounted_soft_savings = []
alert_hours_actual = []
incident_hours_actual = []

for i in range(eval_years):
    months_elapsed = (i + 1) * 12
    if months_elapsed <= st.session_state['implementation_delay_months']:
        ramp_factor = 0
    elif adj_ramp_up_months == 0:
        ramp_factor = 1
    else:
        months_into_benefits = months_elapsed - st.session_state['implementation_delay_months']
        ramp_factor = min(1, months_into_benefits / adj_ramp_up_months)

    alerts = projected_alerts[i]
    incidents = projected_incidents[i]
    alerts_post_reduction = alerts * (1 - adj_alert_reduction_pct / 100)
    incidents_post_reduction = incidents * (1 - adj_incident_reduction_pct / 100)

    alert_hours_saved = ((alerts - alerts_post_reduction) * st.session_state['alert_triage_time_min'] +
                         alerts_post_reduction * st.session_state['alert_triage_time_min'] * adj_triage_time_reduction_pct / 100) / 60
    incident_hours_saved = ((incidents - incidents_post_reduction) * st.session_state['incident_handling_time_min'] +
                            incidents_post_reduction * st.session_state['incident_handling_time_min'] * adj_incident_time_reduction_pct / 100) / 60

    max_alert_fte_hours = st.session_state['fte_total'] * st.session_state['annual_working_hours'] * st.session_state['fte_alerts_pct'] / 100
    max_incident_fte_hours = st.session_state['fte_total'] * st.session_state['annual_working_hours'] * st.session_state['fte_incidents_pct'] / 100

    alert_hours = min(alert_hours_saved, max_alert_fte_hours)
    incident_hours = min(incident_hours_saved, max_incident_fte_hours)

    alert_hours_actual.append(alert_hours)
    incident_hours_actual.append(incident_hours)

    people_efficiency = (alert_hours + incident_hours) * hourly_fte_cost * ramp_factor
    people_efficiency_per_year.append(people_efficiency)

    fte_avoidance = adj_fte_pattern[i] * st.session_state['fte_annual_cost'] * ramp_factor
    ftee_avoidance_per_year.append(fte_avoidance)

    revenue_from_customers = st.session_state[f'customer_growth_year_{i}'] * st.session_state['avg_revenue_per_customer']
    aiops_revenue = revenue_from_customers * adj_aiops_revenue_contribution_pct / 100 * ramp_factor
    aiops_revenue_growth_per_year.append(aiops_revenue)

    tool_savings = adj_tool_savings_per_year[i] * ramp_factor
    tool_savings_annual.append(tool_savings)

    hard_savings = fte_avoidance + aiops_revenue + tool_savings
    hard_savings_per_year.append(hard_savings)

    mttr_reduction_hours = st.session_state['avg_mttr_hours'] * adj_mttr_improvement_pct / 100
    incident_cost_savings = st.session_state['annual_major_incidents'] * mttr_reduction_hours * st.session_state['avg_major_incident_cost_per_hour'] * ramp_factor
    major_incident_savings_per_year.append(incident_cost_savings)

    soft_savings = people_efficiency + incident_cost_savings
    soft_savings_per_year.append(soft_savings)

    total_benefits = hard_savings + soft_savings
    total_benefits_per_year.append(total_benefits)

    year_cost = 0
    if st.session_state['billing_start_month'] <= (i + 1) * 12:
        months_billed = min(12, 12 - max(0, st.session_state['billing_start_month'] - i * 12 - 1))
        year_cost += st.session_state[f'platform_costs_year_{i}'] * months_billed / 12
    if i == 0:
        year_cost += st.session_state['services_cost']
    year_cost += st.session_state['manage_aiops_fte'] * st.session_state['fte_annual_cost']
    costs_per_year.append(year_cost)

    discount = 1 / ((1 + st.session_state['discount_rate'] / 100) ** (i + 1))
    discounted_benefits.append(total_benefits * discount)
    discounted_costs.append(year_cost * discount)
    npv_per_year.append((total_benefits - year_cost) * discount)
    discounted_hard_savings.append(hard_savings * discount)
    discounted_soft_savings.append(soft_savings * discount)

# --- PAYBACK CALCULATION ---
def calculate_monthly_payback(eval_years, implementation_delay_months, ramp_up_months,
                               billing_start_month, total_benefits_per_year,
                               services_cost, manage_aiops_fte, fte_annual_cost, platform_costs):
    monthly_cash_flows = []
    cumulative_total = 0
    total_months = eval_years * 12

    for month in range(1, total_months + 1):
        year_index = (month - 1) // 12
        ramp_factor = 1.0 if ramp_up_months == 0 else min(1.0, max(0, (month - implementation_delay_months) / ramp_up_months))
        monthly_benefit = total_benefits_per_year[year_index] / 12 * ramp_factor if month > implementation_delay_months else 0

        monthly_cost = (manage_aiops_fte * fte_annual_cost) / 12
        if month >= billing_start_month:
            monthly_cost += platform_costs[year_index] / 12
        if month == 1:
            monthly_cost += services_cost

        net_monthly = monthly_benefit - monthly_cost
        cumulative_total += net_monthly
        monthly_cash_flows.append(cumulative_total)

    payback = next((i + 1 for i, v in enumerate(monthly_cash_flows) if v > 0), None)
    return payback

payback_month = calculate_monthly_payback(
    eval_years, st.session_state['implementation_delay_months'], adj_ramp_up_months,
    st.session_state['billing_start_month'], total_benefits_per_year,
    st.session_state['services_cost'], st.session_state['manage_aiops_fte'],
    st.session_state['fte_annual_cost'], [st.session_state[f'platform_costs_year_{i}'] for i in range(eval_years)]
)
st.session_state['payback_period'] = payback_month if payback_month is not None else '> term'


# --- ROI, NPV, and Summary ---
total_disc_costs = sum(discounted_costs)
net_value_total = sum(npv_per_year)
net_value_hard = sum(discounted_hard_savings) - total_disc_costs
net_value_soft = sum(discounted_soft_savings)

roi_total = (net_value_total / total_disc_costs * 100) if total_disc_costs > 0 else 0
roi_hard = (net_value_hard / total_disc_costs * 100) if total_disc_costs > 0 else 0
roi_soft = (sum(discounted_soft_savings) / total_disc_costs * 100) if total_disc_costs > 0 else 0


# Other totals
total_investment = sum(costs_per_year)
total_benefits = sum(total_benefits_per_year)

# Store values in session state for the PDF report
st.session_state['roi'] = roi_total
st.session_state['costs_per_year'] = costs_per_year
st.session_state['total_benefits_per_year'] = total_benefits_per_year
st.session_state['npv_per_year'] = npv_per_year
st.session_state['net_value'] = net_value_total
st.session_state['net_value_hard'] = net_value_hard
st.session_state['net_value_soft'] = sum(discounted_soft_savings)
st.session_state['roi_hard'] = roi_hard
st.session_state['roi_soft'] = roi_soft


if net_value_total > 0 and payback_month is not None:
    recommendation = "✅ RECOMMEND INVESTMENT"
    summary_message = f"Strong business case with {st.session_state['currency_symbol']}{net_value_total:,.0f} total NPV and {payback_month} month payback."
    st.success(f"**{recommendation} ({st.session_state['confidence_level']} Scenario)**")
elif net_value_total > 0:
    recommendation = "⚠️ CONDITIONAL RECOMMENDATION"
    summary_message = f"Positive NPV of {st.session_state['currency_symbol']}{net_value_total:,.0f} but payback exceeds evaluation period."
    st.warning(f"**{recommendation} ({st.session_state['confidence_level']} Scenario)**")
else:
    recommendation = "❌ DO NOT RECOMMEND"
    summary_message = f"Negative NPV of {st.session_state['currency_symbol']}{net_value_total:,.0f}. Investment does not meet financial criteria."
    st.error(f"**{recommendation} ({st.session_state['confidence_level']} Scenario)**")

st.session_state['recommendation'] = recommendation
st.session_state['summary_message'] = summary_message


# --- SUMMARY DISPLAY ---
st.markdown(f"### 💡 Executive Summary ({st.session_state['confidence_level']} Scenario)\n**{summary_message}**")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Investment", f"{st.session_state['currency_symbol']}{total_investment:,.0f}")
    st.metric("Total Benefits", f"{st.session_state['currency_symbol']}{total_benefits:,.0f}")
    st.metric("Payback Period", f"{st.session_state['payback_period']} months")

with col2:
    st.metric("Total Net Present Value", f"{st.session_state['currency_symbol']}{net_value_total:,.0f}")
    st.metric("Hard Savings NPV", f"{st.session_state['currency_symbol']}{net_value_hard:,.0f}",
              help="NPV based on direct cost savings and revenue growth.")
    st.metric("Soft Savings Value (Discounted)", f"{st.session_state['currency_symbol']}{sum(discounted_soft_savings):,.0f}",
              help="Discounted value of productivity and efficiency gains.")

with col3:
    st.metric("Total ROI", f"{roi_total:.1f}%")
    st.metric("Hard Savings ROI", f"{roi_hard:.1f}%",
              help="ROI based on direct cost savings and revenue growth.")
    st.metric("Soft Savings ROI", f"{roi_soft:.1f}%",
              help="Return on investment from productivity and efficiency gains.")


# Breakdown of Key Benefits (original table restored)
with st.expander("View Benefits Breakdown (Summary)"):
    st.write(f"- FTE Avoidance: {st.session_state['currency_symbol']}{sum(ftee_avoidance_per_year):,.0f}")
    st.write(f"- AIOps Revenue: {st.session_state['currency_symbol']}{sum(aiops_revenue_growth_per_year):,.0f}")
    st.write(f"- Tool Savings: {st.session_state['currency_symbol']}{sum(tool_savings_annual):,.0f}")
    st.write(f"- People Efficiency: {st.session_state['currency_symbol']}{sum(people_efficiency_per_year):,.0f}")
    st.write(f"- Major Incident Savings: {st.session_state['currency_symbol']}{sum(major_incident_savings_per_year):,.0f}")


# --- DETAILED BENEFITS BREAKDOWN ---
# This entire section will now dynamically update based on the adjusted variables
st.subheader("Detailed Benefits Breakdown & Calculations")

with st.expander("View FTE Avoidance Calculations"):
    st.markdown("### FTE Avoidance")
    for i in range(eval_years):
        months_elapsed = (i + 1) * 12
        ramp_factor = 1.0 if adj_ramp_up_months == 0 else min(1.0, max(0, (months_elapsed - st.session_state['implementation_delay_months']) / adj_ramp_up_months))
        
        fte_avoidance_calc = adj_fte_pattern[i] * st.session_state['fte_annual_cost'] * ramp_factor
        st.markdown(f"**Year {i+1}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;FTEs Avoided (Adjusted): {adj_fte_pattern[i]:.1f} FTEs")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Annual FTE Cost: {currency_symbol}{st.session_state['fte_annual_cost']:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Ramp-up Factor: {ramp_factor:.2f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Calculation: `{adj_fte_pattern[i]:.1f} FTEs * {currency_symbol}{st.session_state['fte_annual_cost']:,.0f}/FTE * {ramp_factor:.2f} (Ramp-up)`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total FTE Avoidance (Year {i+1}): {currency_symbol}{fte_avoidance_calc:,.0f}**")
        st.markdown("---")
    st.markdown(f"**Overall FTE Avoidance: {currency_symbol}{sum(ftee_avoidance_per_year):,.0f}**")

with st.expander("View AIOps Revenue Growth Calculations"):
    st.markdown("### AIOps Revenue Growth")
    for i in range(eval_years):
        months_elapsed = (i + 1) * 12
        ramp_factor = 1.0 if adj_ramp_up_months == 0 else min(1.0, max(0, (months_elapsed - st.session_state['implementation_delay_months']) / adj_ramp_up_months))
        
        revenue_from_customers = st.session_state[f'customer_growth_year_{i}'] * st.session_state['avg_revenue_per_customer']
        aiops_revenue_calc = revenue_from_customers * adj_aiops_revenue_contribution_pct / 100 * ramp_factor
        
        st.markdown(f"**Year {i+1}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Customer Growth: {st.session_state[f'customer_growth_year_{i}']:,} new customers")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Average Revenue Per Customer: {currency_symbol}{st.session_state['avg_revenue_per_customer']:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;AIOps Revenue Contribution (Adjusted): {adj_aiops_revenue_contribution_pct:.1f}%")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Ramp-up Factor: {ramp_factor:.2f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Calculation: `{st.session_state[f'customer_growth_year_{i}']:,} Customers * {currency_symbol}{st.session_state['avg_revenue_per_customer']:,.0f}/Customer * {adj_aiops_revenue_contribution_pct:.1f}% * {ramp_factor:.2f} (Ramp-up)`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total AIOps Revenue Growth (Year {i+1}): {currency_symbol}{aiops_revenue_calc:,.0f}**")
        st.markdown("---")
    st.markdown(f"**Overall AIOps Revenue Growth: {currency_symbol}{sum(aiops_revenue_growth_per_year):,.0f}**")

with st.expander("View Tool Savings Calculations"):
    st.markdown("### Tool Savings")
    for i in range(eval_years):
        months_elapsed = (i + 1) * 12
        ramp_factor = 1.0 if adj_ramp_up_months == 0 else min(1.0, max(0, (months_elapsed - st.session_state['implementation_delay_months']) / adj_ramp_up_months))
        
        tool_savings_calc = adj_tool_savings_per_year[i] * ramp_factor
        
        st.markdown(f"**Year {i+1}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Annual Tool Savings Input (Adjusted): {currency_symbol}{adj_tool_savings_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Ramp-up Factor: {ramp_factor:.2f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Calculation: `{currency_symbol}{adj_tool_savings_per_year[i]:,.0f} * {ramp_factor:.2f} (Ramp-up)`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Tool Savings (Year {i+1}): {currency_symbol}{tool_savings_calc:,.0f}**")
        st.markdown("---")
    st.markdown(f"**Overall Tool Savings: {currency_symbol}{sum(tool_savings_annual):,.0f}**")

with st.expander("View People Efficiency Calculations"):
    st.markdown("### People Efficiency (Productivity Gains)")
    for i in range(eval_years):
        months_elapsed = (i + 1) * 12
        ramp_factor = 1.0 if adj_ramp_up_months == 0 else min(1.0, max(0, (months_elapsed - st.session_state['implementation_delay_months']) / adj_ramp_up_months))

        alerts = total_customers_in_year[i] * st.session_state['annual_alerts_per_customer']
        incidents = total_customers_in_year[i] * st.session_state['annual_incidents_per_customer']
        
        alerts_post_reduction = alerts * (1 - adj_alert_reduction_pct / 100)
        incidents_post_reduction = incidents * (1 - adj_incident_reduction_pct / 100)

        alert_hours_saved_from_volume = (alerts - alerts_post_reduction) * st.session_state['alert_triage_time_min'] / 60
        alert_hours_saved_from_efficiency = alerts_post_reduction * st.session_state['alert_triage_time_min'] * adj_triage_time_reduction_pct / 100 / 60
        total_alert_hours_saved = alert_hours_saved_from_volume + alert_hours_saved_from_efficiency
        
        incident_hours_saved_from_volume = (incidents - incidents_post_reduction) * st.session_state['incident_handling_time_min'] / 60
        incident_hours_saved_from_efficiency = incidents_post_reduction * st.session_state['incident_handling_time_min'] * adj_incident_time_reduction_pct / 100 / 60
        total_incident_hours_saved = incident_hours_saved_from_volume + incident_hours_saved_from_efficiency

        capped_alert_hours = min(total_alert_hours_saved, st.session_state['fte_total'] * st.session_state['annual_working_hours'] * st.session_state['fte_alerts_pct'] / 100)
        capped_incident_hours = min(total_incident_hours_saved, st.session_state['fte_total'] * st.session_state['annual_working_hours'] * st.session_state['fte_incidents_pct'] / 100)

        total_efficiency_hours = (capped_alert_hours + capped_incident_hours)
        people_efficiency_calc = total_efficiency_hours * hourly_fte_cost * ramp_factor

        st.markdown(f"**Year {i+1}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Alert Efficiency:**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Total Alerts (initial): {alerts:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Alert Reduction (Adjusted): {adj_alert_reduction_pct:.1f}%")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Alerts after Reduction: {alerts_post_reduction:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Triage Time per Alert: {st.session_state['alert_triage_time_min']} min")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Triage Time Reduction (Adjusted): {adj_triage_time_reduction_pct:.1f}%")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Hours Saved (Volume): `{alert_hours_saved_from_volume:,.0f} hours`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Hours Saved (Efficiency): `{alert_hours_saved_from_efficiency:,.0f} hours`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Total Alert Hours Saved: `{total_alert_hours_saved:,.0f} hours` (Capped at {capped_alert_hours:,.0f} hours based on FTE allocation)")
        
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Incident Efficiency:**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Total Incidents (initial): {incidents:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Incident Reduction (Adjusted): {adj_incident_reduction_pct:.1f}%")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Incidents after Reduction: {incidents_post_reduction:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Handling Time per Incident: {st.session_state['incident_handling_time_min']} min")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Handling Time Reduction (Adjusted): {adj_incident_time_reduction_pct:.1f}%")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Hours Saved (Volume): `{incident_hours_saved_from_volume:,.0f} hours`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Hours Saved (Efficiency): `{incident_hours_saved_from_efficiency:,.0f} hours`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Total Incident Hours Saved: `{total_incident_hours_saved:,.0f} hours` (Capped at {capped_incident_hours:,.0f} hours based on FTE allocation)")
        
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Total FTE Hours Saved: `{total_efficiency_hours:,.0f} hours`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Hourly FTE Cost: {currency_symbol}{hourly_fte_cost:,.2f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Ramp-up Factor: {ramp_factor:.2f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Calculation: `{total_efficiency_hours:,.0f} hours * {currency_symbol}{hourly_fte_cost:,.2f}/hour * {ramp_factor:.2f} (Ramp-up)`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total People Efficiency (Year {i+1}): {currency_symbol}{people_efficiency_calc:,.0f}**")
        st.markdown("---")
    st.markdown(f"**Overall People Efficiency: {currency_symbol}{sum(people_efficiency_per_year):,.0f}**")

with st.expander("View Major Incident Savings Calculations"):
    st.markdown("### Major Incident Savings")
    for i in range(eval_years):
        months_elapsed = (i + 1) * 12
        ramp_factor = 1.0 if adj_ramp_up_months == 0 else min(1.0, max(0, (months_elapsed - st.session_state['implementation_delay_months']) / adj_ramp_up_months))
        
        mttr_reduction_hours = st.session_state['avg_mttr_hours'] * adj_mttr_improvement_pct / 100
        incident_cost_savings_calc = st.session_state['annual_major_incidents'] * mttr_reduction_hours * st.session_state['avg_major_incident_cost_per_hour'] * ramp_factor
        
        st.markdown(f"**Year {i+1}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Annual Major Incidents: {st.session_state['annual_major_incidents']}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Average MTTR (hours): {st.session_state['avg_mttr_hours']:.1f} hours")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;MTTR Improvement (Adjusted): {adj_mttr_improvement_pct:.1f}%")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;MTTR Reduction (hours): `{st.session_state['avg_mttr_hours']:.1f} hours * {adj_mttr_improvement_pct:.1f}% = {mttr_reduction_hours:.1f} hours`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Average Major Incident Cost per Hour: {currency_symbol}{st.session_state['avg_major_incident_cost_per_hour']:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Ramp-up Factor: {ramp_factor:.2f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Calculation: `{st.session_state['annual_major_incidents']} Incidents * {mttr_reduction_hours:.1f} hours * {currency_symbol}{st.session_state['avg_major_incident_cost_per_hour']:,.0f}/hour * {ramp_factor:.2f} (Ramp-up)`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Major Incident Savings (Year {i+1}): {currency_symbol}{incident_cost_savings_calc:,.0f}**")
        st.markdown("---")
    st.markdown(f"**Overall Major Incident Savings: {currency_symbol}{sum(major_incident_savings_per_year):,.0f}**")

with st.expander("View Net Present Value (NPV) Calculations"):
    st.markdown("### Net Present Value (NPV)")
    st.markdown(f"**Discount Rate: {st.session_state['discount_rate']}%**")
    st.markdown("---")
    for i in range(eval_years):
        discount = 1 / ((1 + st.session_state['discount_rate'] / 100) ** (i + 1))
        
        # Total NPV for the year
        total_npv_year = (total_benefits_per_year[i] - costs_per_year[i]) * discount
        st.markdown(f"**Year {i+1}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Benefits Breakdown (Year {i+1}):**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- FTE Avoidance: {currency_symbol}{ftee_avoidance_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- AIOps Revenue: {currency_symbol}{aiops_revenue_growth_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Tool Savings: {currency_symbol}{tool_savings_annual[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- People Efficiency: {currency_symbol}{people_efficiency_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Major Incident Savings: {currency_symbol}{major_incident_savings_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Benefits (Year {i+1}): {currency_symbol}{total_benefits_per_year[i]:,.0f}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Costs (Year {i+1}): {currency_symbol}{costs_per_year[i]:,.0f}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Discount Factor (Year {i+1}): `1 / (1 + {st.session_state['discount_rate']}/100)^{i+1} = {discount:.4f}`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Calculation: `({currency_symbol}{total_benefits_per_year[i]:,.0f} (Benefits) - {currency_symbol}{costs_per_year[i]:,.0f} (Costs)) * {discount:.4f} (Discount Factor)`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Net Present Value (Year {i+1}): {currency_symbol}{total_npv_year:,.0f}**")
        st.markdown("---")
    st.markdown(f"**Overall Total Net Present Value: {currency_symbol}{net_value_total:,.0f}**")
    st.markdown("---")

    st.markdown("### Hard Savings NPV")
    for i in range(eval_years):
        discount = 1 / ((1 + st.session_state['discount_rate'] / 100) ** (i + 1))
        hard_savings_npv_year = hard_savings_per_year[i] * discount
        st.markdown(f"**Year {i+1}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Hard Savings Breakdown (Year {i+1}):**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- FTE Avoidance: {currency_symbol}{ftee_avoidance_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- AIOps Revenue: {currency_symbol}{aiops_revenue_growth_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Tool Savings: {currency_symbol}{tool_savings_annual[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Hard Savings (Year {i+1}): {currency_symbol}{hard_savings_per_year[i]:,.0f}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Discount Factor: {discount:.4f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Calculation: `{currency_symbol}{hard_savings_per_year[i]:,.0f} (Hard Savings) * {discount:.4f} (Discount Factor)`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Discounted Hard Savings (Year {i+1}): {currency_symbol}{hard_savings_npv_year:,.0f}**")
        st.markdown("---")
    st.markdown(f"**Total Discounted Hard Savings: {currency_symbol}{sum(discounted_hard_savings):,.0f}**")
    st.markdown(f"**Total Discounted Costs: {currency_symbol}{total_disc_costs:,.0f}**")
    st.markdown(f"**Hard Savings NPV Calculation: `{currency_symbol}{sum(discounted_hard_savings):,.0f} (Total Discounted Hard Savings) - {currency_symbol}{total_disc_costs:,.0f} (Total Discounted Costs)`**")
    st.markdown(f"**Overall Hard Savings NPV: {currency_symbol}{net_value_hard:,.0f}**")
    st.markdown("---")

    st.markdown("### Soft Savings NPV")
    for i in range(eval_years):
        discount = 1 / ((1 + st.session_state['discount_rate'] / 100) ** (i + 1))
        soft_savings_npv_year = soft_savings_per_year[i] * discount
        st.markdown(f"**Year {i+1}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Soft Savings Breakdown (Year {i+1}):**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- People Efficiency: {currency_symbol}{people_efficiency_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Major Incident Savings: {currency_symbol}{major_incident_savings_per_year[i]:,.0f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Soft Savings (Year {i+1}): {currency_symbol}{soft_savings_per_year[i]:,.0f}**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Discount Factor: {discount:.4f}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Calculation: `{currency_symbol}{soft_savings_per_year[i]:,.0f} (Soft Savings) * {discount:.4f} (Discount Factor)`")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Discounted Soft Savings (Year {i+1}): {currency_symbol}{soft_savings_npv_year:,.0f}**")
        st.markdown("---")
    st.markdown(f"**Overall Soft Savings NPV (Discounted Value): {currency_symbol}{net_value_soft:,.0f}**")


with st.expander("View Return on Investment (ROI) Calculations"):
    st.markdown("### Return on Investment (ROI)")
    st.markdown(f"**Discount Rate: {st.session_state['discount_rate']}%**")
    st.markdown(f"**Total Discounted Costs (Denominator for ROI): {currency_symbol}{total_disc_costs:,.0f}**")
    st.markdown("---")

    st.markdown("### Total ROI")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Net Present Value (NPV):** This is the sum of discounted net cash flows over the evaluation period. It represents the value added by the project in today's currency. You can view its detailed calculation in the 'View Net Present Value (NPV) Calculations' section above.")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Value: {currency_symbol}{net_value_total:,.0f}")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Discounted Costs:** This is the sum of all project costs, discounted back to the present day. It represents the true cost of the investment in today's terms. You can view its detailed calculation in the 'View Net Present Value (NPV) Calculations' section above.")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Value: {currency_symbol}{total_disc_costs:,.0f}")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Formula:** `ROI = (Total NPV / Total Discounted Costs) * 100`")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Calculation:** `({currency_symbol}{net_value_total:,.0f} / {currency_symbol}{total_disc_costs:,.0f}) * 100`")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Overall Total ROI: {roi_total:.1f}%**")
    st.markdown("---")

    st.markdown("### Hard Savings ROI")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Hard Savings NPV:** This represents the Net Present Value derived specifically from direct, quantifiable savings and revenue growth (FTE avoidance, AIOps revenue, tool savings). This value is calculated as `Total Discounted Hard Savings - Total Discounted Costs`.")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Value: {currency_symbol}{net_value_hard:,.0f}")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Discounted Costs:** (As defined above) {currency_symbol}{total_disc_costs:,.0f}")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Formula:** `ROI = (Hard Savings NPV / Total Discounted Costs) * 100`")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Calculation:** `({currency_symbol}{net_value_hard:,.0f} / {currency_symbol}{total_disc_costs:,.0f}) * 100`")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Overall Hard Savings ROI: {roi_hard:.1f}%**")
    st.markdown("---")

    st.markdown("### Soft Savings ROI")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Discounted Soft Savings:** This is the sum of the discounted values of indirect, productivity-related benefits (people efficiency, major incident savings). Since these are often considered benefits without direct, separate costs, their ROI is calculated against the overall investment costs.")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Value: {currency_symbol}{net_value_soft:,.0f}")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Total Discounted Costs:** (As defined above) {currency_symbol}{total_disc_costs:,.0f}")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Formula:** `ROI = (Total Discounted Soft Savings / Total Discounted Costs) * 100`")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Calculation:** `({currency_symbol}{net_value_soft:,.0f} / {currency_symbol}{total_disc_costs:,.0f}) * 100`")
    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**Overall Soft Savings ROI: {roi_soft:.1f}%**")


# --- FINAL DATAFRAME ---
df = pd.DataFrame({
    "Year": [f"Year {i+1}" for i in range(eval_years)],
    "Hard Savings": hard_savings_per_year,
    "Soft Savings": soft_savings_per_year,
    "Total Benefits": total_benefits_per_year,
    "Costs": costs_per_year,
    "Net Cash Flow": [b - c for b, c in zip(total_benefits_per_year, costs_per_year)],
    "NPV": npv_per_year
})

# Rename columns for better presentation
df.rename(columns={'NPV': 'Discounted Net Value'}, inplace=True)


df_display = df.copy()
for col in df_display.columns:
    if col != 'Year':
        df_display[col] = df_display[col].apply(lambda x: f"{st.session_state['currency_symbol']}{x:,.0f}")

st.subheader("📊 Yearly Financial Breakdown")
st.dataframe(df_display, use_container_width=True)

# Save the display version to session state for the PDF
st.session_state['df_data'] = df_display

# --- BUSINESS VALUE STORIES ---
# This section will also dynamically update
st.subheader("⭐ Business Value Stories")

# Calculate total benefits for use in stories
total_fte_avoidance = sum(ftee_avoidance_per_year)
total_aiops_revenue = sum(aiops_revenue_growth_per_year)
total_tool_savings = sum(tool_savings_annual)
total_people_efficiency = sum(people_efficiency_per_year)
total_major_incident_savings = sum(major_incident_savings_per_year)

# Dynamic CIO Story
cio_story_parts = [
    f"As CIO, your primary focus is on driving technological innovation while ensuring operational excellence and strategic alignment. This assessment is based on a '{st.session_state['confidence_level']}' scenario."
]

if st.session_state['recommendation'] == "✅ RECOMMEND INVESTMENT":
    cio_story_parts.append("This AIOps platform can be a game-changer for your organization, not just for its technical capabilities but also for its strong financial backing.")
else:
    cio_story_parts.append("This AIOps platform offers critical capabilities to enhance your IT resilience and operational efficiency.")

# Add dynamic details based on specific benefits
if adj_mttr_improvement_pct > 0:
    cio_story_parts.append(f"It promises to significantly reduce your Mean Time To Resolution (MTTR) by {adj_mttr_improvement_pct:.1f}%, meaning your critical systems recover faster, directly impacting business continuity and customer satisfaction.")
if adj_alert_reduction_pct > 0 or adj_incident_reduction_pct > 0:
    alert_incident_details = []
    if adj_alert_reduction_pct > 0:
        alert_incident_details.append(f"alert volume by {adj_alert_reduction_pct:.1f}%")
    if adj_incident_reduction_pct > 0:
        alert_incident_details.append(f"incident volume by {adj_incident_reduction_pct:.1f}%")
    if alert_incident_details:
        cio_story_parts.append(f"Furthermore, by automating alert correlation and incident remediation, your organization can anticipate a substantial reduction in {', and '.join(alert_incident_details)}.")

if total_fte_avoidance > 0 or total_people_efficiency > 0:
    fte_efficiency_details = []
    if total_fte_avoidance > 0:
        fte_efficiency_details.append("FTE avoidance")
    if total_people_efficiency > 0:
        fte_efficiency_details.append("improved people efficiency")
    if fte_efficiency_details:
        cio_story_parts.append(f"This frees up your valuable engineering talent from reactive firefighting, allowing your team to focus on strategic initiatives and innovation through {', and '.join(fte_efficiency_details)}.")

if total_major_incident_savings > 0:
    cio_story_parts.append(f"The platform also provides the necessary data and insights to make proactive decisions, improving your overall IT resilience and minimizing the impact of major incidents, contributing to significant savings.")

if st.session_state['recommendation'] == "✅ RECOMMEND INVESTMENT":
    cio_story_parts.append("All while delivering a strong ROI for your investment.")
else:
    cio_story_parts.append(f"While these operational improvements are desirable, the current financial model indicates a negative Net Present Value of {st.session_state['currency_symbol']}{net_value_total:,.0f} and an ROI of {roi_total:.1f}%. This suggests that the strategic benefits, while real, are not currently sufficient to justify the investment from a purely financial standpoint. You may need to re-evaluate the cost structure or expected benefits to make this a viable investment for your strategic objectives.")

cio_story_default = " ".join(cio_story_parts)
st.session_state['cio_story'] = st.text_area("For the CIO", value=cio_story_default, height=250, key='cio_story_input')

# Dynamic CFO Story
if st.session_state['recommendation'] == "✅ RECOMMEND INVESTMENT":
    cfo_story_parts = [
        f"From a CFO's perspective, this AIOps investment presents a compelling financial case for your organization, based on a '{st.session_state['confidence_level']}' scenario.",
        f"With a projected Net Present Value (NPV) of {st.session_state['currency_symbol']}{net_value_total:,.0f} and an impressive Return on Investment (ROI) of {roi_total:.1f}% over {eval_years} years, this is a financially sound decision.",
        f"The payback period of {st.session_state['payback_period']} months demonstrates a quick return on your capital."
    ]
    
    hard_savings_details = []
    if total_fte_avoidance > 0:
        hard_savings_details.append(f"{st.session_state['currency_symbol']}{total_fte_avoidance:,.0f} from FTE avoidance")
    if total_tool_savings > 0:
        hard_savings_details.append(f"{st.session_state['currency_symbol']}{total_tool_savings:,.0f} in tool consolidation")
    if total_aiops_revenue > 0:
        hard_savings_details.append(f"{st.session_state['currency_symbol']}{total_aiops_revenue:,.0f} in AIOps-attributed revenue growth")

    if hard_savings_details:
        cfo_story_parts.append(f"Your organization can anticipate significant hard savings including {', '.join(hard_savings_details)}.")
    else:
        cfo_story_parts.append("While direct hard savings are not currently projected, the investment's value is driven by operational efficiencies.")

    cfo_story_parts.append(f"Beyond these direct savings, the platform will drive operational efficiencies, reducing major incident costs by {st.session_state['currency_symbol']}{total_major_incident_savings:,.0f} and improving overall productivity, contributing to a healthier bottom line for your business.")
    cfo_story_default = " ".join(cfo_story_parts)

elif st.session_state['recommendation'] == "⚠️ CONDITIONAL RECOMMENDATION":
    cfo_story_parts = [
        f"While this AIOps investment shows a positive Net Present Value (NPV) of {st.session_state['currency_symbol']}{net_value_total:,.0f} based on a '{st.session_state['confidence_level']}' scenario,",
        f"the payback period of {st.session_state['payback_period']} months extends beyond your typical short-term return expectations."
    ]

    hard_savings_details = []
    if total_fte_avoidance > 0:
        hard_savings_details.append(f"FTE avoidance ({st.session_state['currency_symbol']}{total_fte_avoidance:,.0f})")
    if total_tool_savings > 0:
        hard_savings_details.append(f"tool consolidation ({st.session_state['currency_symbol']}{total_tool_savings:,.0f})")
    if total_aiops_revenue > 0:
        hard_savings_details.append(f"potential revenue growth ({st.session_state['currency_symbol']}{total_aiops_revenue:,.0f})")

    if hard_savings_details:
        cfo_story_parts.append(f"However, the strategic benefits, including significant hard savings from {', '.join(hard_savings_details)}, still make this a worthwhile consideration for your long-term value and operational efficiency improvements.")
    else:
        cfo_story_parts.append("However, the strategic benefits from operational efficiency improvements still make this a worthwhile consideration for your long-term value, even without direct hard savings.")
    cfo_story_default = " ".join(cfo_story_parts)

else: # "❌ DO NOT RECOMMEND"
    cfo_story_default = (
        f"From a financial perspective, this AIOps investment currently does not meet your financial criteria under a '{st.session_state['confidence_level']}' scenario, "
        f"showing a negative Net Present Value (NPV) of {st.session_state['currency_symbol']}{net_value_total:,.0f} and an ROI of {roi_total:.1f}%. "
        "You may need to re-evaluate the cost structure or expected benefits to make this a viable investment. "
        "While operational efficiencies and reduced major incident costs are desirable, the current financial model indicates a need for re-assessment "
        "to achieve a positive return for your organization. The projected benefits, including "
        f"{st.session_state['currency_symbol']}{total_fte_avoidance:,.0f} from FTE avoidance, "
        f"{st.session_state['currency_symbol']}{total_tool_savings:,.0f} in tool consolidation, and "
        f"{st.session_state['currency_symbol']}{total_aiops_revenue:,.0f} in AIOps-attributed revenue growth, "
        "are not sufficient to offset the costs and deliver a positive financial outcome for your business at this time."
    )
st.session_state['cfo_story'] = st.text_area("For the CFO", value=cfo_story_default, height=250, key='cfo_story_input')

# Dynamic Head of Support Story
if st.session_state['recommendation'] in ["✅ RECOMMEND INVESTMENT", "⚠️ CONDITIONAL RECOMMENDATION"]:
    head_of_support_story_default = (
        f"As Head of Support, your priority is empowering your teams to deliver exceptional service efficiently. Based on a '{st.session_state['confidence_level']}' scenario, "
        "this AIOps platform will revolutionize how your support teams operate. By reducing alert noise and automating routine tasks, "
        f"your organization can expect a {adj_triage_time_reduction_pct:.1f}% reduction in alert triage time and a {adj_incident_time_reduction_pct:.1f}% "
        "reduction in incident handling time. This means your engineers can resolve issues faster, "
        "leading to improved customer satisfaction and reduced burnout for your staff. "
        "The proactive identification of issues will also minimize the impact of major incidents, "
        "making your support operations more stable and predictable. This investment allows your team to shift from reactive problem-solving "
        "to proactive service delivery, enhancing your team's effectiveness and job satisfaction, and contributing to the overall positive business case for your organization."
    )
else: # "❌ DO NOT RECOMMEND"
    head_of_support_story_default = (
        f"As Head of Support, your priority is empowering your teams to deliver exceptional service efficiently. Even under a '{st.session_state['confidence_level']}' scenario, "
        "this AIOps platform offers significant potential to revolutionize how your support teams operate. "
        f"By reducing alert noise and automating routine tasks, your organization *could* see a {adj_triage_time_reduction_pct:.1f}% reduction in alert triage time "
        f"and a {adj_incident_time_reduction_pct:.1f}% reduction in incident handling time. This would allow your engineers to resolve issues faster, "
        "leading to improved customer satisfaction and reduced burnout for your staff. "
        "The proactive identification of issues would also minimize the impact of major incidents, "
        "making your support operations more stable and predictable. However, despite these operational benefits, "
        "the overall financial analysis indicates that the investment does not currently meet your financial thresholds, "
        f"with a negative Net Present Value of {st.session_state['currency_symbol']}{net_value_total:,.0f}. "
        "This means that while the operational gains are clear, they are not sufficient to justify the investment without further optimization of costs or a re-evaluation of expected financial returns for your business."
    )
st.session_state['head_of_support_story'] = st.text_area("For the Head of Support", value=head_of_support_story_default, height=250, key='head_of_support_story_input')
