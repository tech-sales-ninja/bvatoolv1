# v2.3 - Enhanced with FTE Time Allocation Percentage

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import io
from datetime import datetime
import csv
from io import StringIO
import json

# Executive Report Dependencies
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    import matplotlib.pyplot as plt
    from io import BytesIO
    REPORT_DEPENDENCIES_AVAILABLE = True
except ImportError:
    REPORT_DEPENDENCIES_AVAILABLE = False

# Set page configuration
st.set_page_config(page_title="Autonomous IT Operations BVA Tool", layout="wide")

# --- ENHANCED VALIDATION FUNCTIONS ---

def validate_inputs():
    """Validate user inputs and return warnings/errors"""
    warnings = []
    errors = []
    
    # Get values from session state
    platform_cost = st.session_state.get('platform_cost', 0)
    services_cost = st.session_state.get('services_cost', 0)
    alert_reduction_pct = st.session_state.get('alert_reduction_pct', 0)
    incident_reduction_pct = st.session_state.get('incident_reduction_pct', 0)
    mttr_improvement_pct = st.session_state.get('mttr_improvement_pct', 0)
    alert_volume = st.session_state.get('alert_volume', 0)
    alert_ftes = st.session_state.get('alert_ftes', 0)
    incident_volume = st.session_state.get('incident_volume', 0)
    incident_ftes = st.session_state.get('incident_ftes', 0)
    working_hours_per_fte_per_year = st.session_state.get('working_hours_per_fte_per_year', 2000)
    avg_alert_triage_time = st.session_state.get('avg_alert_triage_time', 0)
    avg_incident_triage_time = st.session_state.get('avg_incident_triage_time', 0)
    billing_start_month = st.session_state.get('billing_start_month', 1)
    implementation_delay_months = st.session_state.get('implementation_delay', 6)
    benefits_ramp_up_months = st.session_state.get('benefits_ramp_up', 3)
    evaluation_years = st.session_state.get('evaluation_years', 3)
    
    # Check for negative values where they don't make sense
    if platform_cost < 0:
        errors.append("Platform cost cannot be negative")
    if services_cost < 0:
        errors.append("Services cost cannot be negative")
    
    # Check for unrealistic percentages
    if alert_reduction_pct > 90:
        warnings.append("Alert reduction >90% may be unrealistic")
    if incident_reduction_pct > 90:
        warnings.append("Incident reduction >90% may be unrealistic")
    if mttr_improvement_pct > 80:
        warnings.append("MTTR improvement >80% may be unrealistic")
    
    # Check for missing critical inputs
    if platform_cost == 0 and services_cost == 0:
        warnings.append("Both platform and services costs are zero - is this correct?")
    
    # Check for inconsistent FTE data
    if alert_volume > 0 and alert_ftes == 0:
        warnings.append("You have alert volume but no FTEs assigned to alerts")
    if incident_volume > 0 and incident_ftes == 0:
        warnings.append("You have incident volume but no FTEs assigned to incidents")
    
    # Check working hours logic
    if working_hours_per_fte_per_year < 1000:
        warnings.append("Working hours per FTE seems very low (<1000 hours/year)")
    if working_hours_per_fte_per_year > 3000:
        warnings.append("Working hours per FTE seems very high (>3000 hours/year)")
    
    # Check alert/incident time logic
    if alert_volume > 0 and avg_alert_triage_time == 0:
        warnings.append("Alert volume exists but triage time is zero")
    if incident_volume > 0 and avg_incident_triage_time == 0:
        warnings.append("Incident volume exists but triage time is zero")
    
    # Add billing start month validation
    if billing_start_month < implementation_delay_months:
        warnings.append(f"You'll pay platform costs from month {billing_start_month} but get benefits from month {implementation_delay_months + 1}")
    
    if billing_start_month > evaluation_years * 12:
        errors.append(f"Billing start month ({billing_start_month}) is beyond evaluation period ({evaluation_years * 12} months)")
    
    if billing_start_month > implementation_delay_months + benefits_ramp_up_months:
        warnings.append(f"Billing starts (month {billing_start_month}) after full benefits realization (month {implementation_delay_months + benefits_ramp_up_months}) - unusual scenario")
    
    return warnings, errors

def check_calculation_health():
    """Check if calculations produce reasonable results"""
    issues = []
    
    # Get values from session state with defaults
    alert_fte_percentage = st.session_state.get('alert_fte_percentage', 0)
    incident_fte_percentage = st.session_state.get('incident_fte_percentage', 0)
    total_annual_benefits = st.session_state.get('total_annual_benefits', 0)
    avg_alert_fte_salary = st.session_state.get('avg_alert_fte_salary', 0)
    alert_ftes = st.session_state.get('alert_ftes', 0)
    avg_incident_fte_salary = st.session_state.get('avg_incident_fte_salary', 0)
    incident_ftes = st.session_state.get('incident_ftes', 0)
    
    # Check if time allocation exceeds 100%
    if alert_fte_percentage > 1.0:
        issues.append(f"Alert management requires {alert_fte_percentage*100:.1f}% of allocated FTE time (>100%)")
    if incident_fte_percentage > 1.0:
        issues.append(f"Incident management requires {incident_fte_percentage*100:.1f}% of allocated FTE time (>100%)")
    
    # Check if benefits seem unrealistically high
    total_fte_costs = avg_alert_fte_salary * alert_ftes + avg_incident_fte_salary * incident_ftes
    if total_fte_costs > 0 and total_annual_benefits > total_fte_costs * 2:
        issues.append("Total annual benefits exceed 2x total FTE costs - please verify assumptions")
    
    return issues

# --- NEW: RED FLAG DETECTION FUNCTIONS ---

def detect_calculation_red_flags():
    """Detect unrealistic calculations and provide detailed reasoning"""
    red_flags = []
    warnings = []
    
    # Get values from session state
    cost_per_alert = st.session_state.get('cost_per_alert', 0)
    cost_per_incident = st.session_state.get('cost_per_incident', 0)
    alert_fte_percentage = st.session_state.get('alert_fte_percentage', 0)
    incident_fte_percentage = st.session_state.get('incident_fte_percentage', 0)
    total_annual_benefits = st.session_state.get('total_annual_benefits', 0)
    alert_ftes = st.session_state.get('alert_ftes', 0)
    incident_ftes = st.session_state.get('incident_ftes', 0)
    avg_alert_fte_salary = st.session_state.get('avg_alert_fte_salary', 0)
    avg_incident_fte_salary = st.session_state.get('avg_incident_fte_salary', 0)
    alert_fte_time_pct = st.session_state.get('alert_fte_time_pct', 100)
    incident_fte_time_pct = st.session_state.get('incident_fte_time_pct', 100)
    alert_volume = st.session_state.get('alert_volume', 0)
    incident_volume = st.session_state.get('incident_volume', 0)
    avg_alert_triage_time = st.session_state.get('avg_alert_triage_time', 0)
    avg_incident_triage_time = st.session_state.get('avg_incident_triage_time', 0)
    working_hours_per_fte_per_year = st.session_state.get('working_hours_per_fte_per_year', 2000)
    currency_symbol = st.session_state.get('currency', '$')
    
    # Red Flag 1: Extremely high cost per alert/incident
    if cost_per_alert > 100:
        reasoning_text = f"""Your calculated cost per alert is {currency_symbol}{cost_per_alert:.2f}, which seems very high.

**How this is calculated:**
- Annual FTE cost for alerts: {currency_symbol}{alert_ftes * avg_alert_fte_salary:,.0f}
- % of time on alerts (your input): {alert_fte_time_pct}%
- Cost allocated to alerts: {currency_symbol}{alert_ftes * avg_alert_fte_salary * (alert_fte_time_pct / 100.0):,.0f}
- Cost per alert: Allocated Cost / Alert Volume

**Likely issues:**
- % of FTE Time on Alerts ({alert_fte_time_pct}%) may be too high for the volume
- Number of FTEs ({alert_ftes}) may be too high
- FTE salaries ({currency_symbol}{avg_alert_fte_salary:,.0f}) may be inflated
- Alert volume ({alert_volume:,}) may be too low for the allocated cost

**Industry benchmarks:** Alert costs typically range from {currency_symbol}0.50 to {currency_symbol}15.00"""
        
        red_flags.append({
            'type': 'High Cost Per Alert',
            'value': f"{currency_symbol}{cost_per_alert:.2f}",
            'reasoning': reasoning_text,
            'severity': 'high'
        })
    
    if cost_per_incident > 500:
        reasoning_text = f"""Your calculated cost per incident is {currency_symbol}{cost_per_incident:.2f}, which seems very high.

**How this is calculated:**
- Annual FTE cost for incidents: {currency_symbol}{incident_ftes * avg_incident_fte_salary:,.0f}
- % of time on incidents (your input): {incident_fte_time_pct}%
- Cost allocated to incidents: {currency_symbol}{incident_ftes * avg_incident_fte_salary * (incident_fte_time_pct / 100.0):,.0f}
- Cost per incident: Allocated Cost / Incident Volume

**Likely issues:**
- % of FTE Time on Incidents ({incident_fte_time_pct}%) may be too high for the volume
- Number of FTEs ({incident_ftes}) may be too high
- FTE salaries ({currency_symbol}{avg_incident_fte_salary:,.0f}) may be inflated
- Incident volume ({incident_volume:,}) may be too low for the allocated cost

**Industry benchmarks:** Incident costs typically range from {currency_symbol}5.00 to {currency_symbol}200.00"""
        
        red_flags.append({
            'type': 'High Cost Per Incident',
            'value': f"{currency_symbol}{cost_per_incident:.2f}",
            'reasoning': reasoning_text,
            'severity': 'high'
        })
    
    # Red Flag 2: FTE utilization over 100%
    if alert_fte_percentage > 1.0:
        reasoning_text = f"""Your alert workload requires more time than you've allocated.

**The Math Breakdown:**
- **Time Needed for Workload:** {alert_volume:,} alerts × {avg_alert_triage_time} mins/alert = {alert_volume * avg_alert_triage_time / 60:,.0f} hours/year
- **FTE Time Allocated to Alerts:** {alert_ftes} FTEs × {working_hours_per_fte_per_year:,.0f} hours/FTE × {alert_fte_time_pct}% = **{(alert_ftes * working_hours_per_fte_per_year * alert_fte_time_pct / 100.0):,.0f} hours/year**
- **Utilization of Allocated Time:** {alert_volume * avg_alert_triage_time / 60:,.0f} hours ÷ {(alert_ftes * working_hours_per_fte_per_year * alert_fte_time_pct / 100.0):,.0f} hours = **{alert_fte_percentage*100:.1f}%**

**To fix this, you need to:**
- Increase the **% of FTE Time on Alerts** (currently {alert_fte_time_pct}%)
- Increase the number of FTEs managing alerts (currently {alert_ftes})
- Reduce the average triage time per alert (currently {avg_alert_triage_time} minutes)
- Reduce the alert volume (currently {alert_volume:,})"""
        
        red_flags.append({
            'type': 'Over-allocated Alert FTEs',
            'value': f"{alert_fte_percentage*100:.1f}% Utilization of Allocated Time",
            'reasoning': reasoning_text,
            'severity': 'critical'
        })
    
    if incident_fte_percentage > 1.0:
        reasoning_text = f"""Your incident workload requires more time than you've allocated.

**The Math Breakdown:**
- **Time Needed for Workload:** {incident_volume:,} incidents × {avg_incident_triage_time} mins/incident = {incident_volume * avg_incident_triage_time / 60:,.0f} hours/year
- **FTE Time Allocated to Incidents:** {incident_ftes} FTEs × {working_hours_per_fte_per_year:,.0f} hours/FTE × {incident_fte_time_pct}% = **{(incident_ftes * working_hours_per_fte_per_year * incident_fte_time_pct / 100.0):,.0f} hours/year**
- **Utilization of Allocated Time:** {incident_volume * avg_incident_triage_time / 60:,.0f} hours ÷ {(incident_ftes * working_hours_per_fte_per_year * incident_fte_time_pct / 100.0):,.0f} hours = **{incident_fte_percentage*100:.1f}%**

**To fix this, you need to:**
- Increase the **% of FTE Time on Incidents** (currently {incident_fte_time_pct}%)
- Increase the number of FTEs managing incidents (currently {incident_ftes})
- Reduce the average triage time per incident (currently {avg_incident_triage_time} minutes)
- Reduce the incident volume (currently {incident_volume:,})"""

        red_flags.append({
            'type': 'Over-allocated Incident FTEs',
            'value': f"{incident_fte_percentage*100:.1f}% Utilization of Allocated Time",
            'reasoning': reasoning_text,
            'severity': 'critical'
        })
    
    # Red Flag 3: Benefits seem disproportionately high
    total_fte_costs = (alert_ftes * avg_alert_fte_salary) + (incident_ftes * avg_incident_fte_salary)
    if total_fte_costs > 0 and total_annual_benefits > total_fte_costs * 3:
        reasoning_text = f"""Your total annual benefits ({currency_symbol}{total_annual_benefits:,.0f}) are {total_annual_benefits/total_fte_costs:.1f}x your total FTE costs.

**This seems unrealistic because:**
- Total FTE costs: {currency_symbol}{total_fte_costs:,.0f}
- Total benefits: {currency_symbol}{total_annual_benefits:,.0f}
- Ratio: {total_annual_benefits/total_fte_costs:.1f}:1

**Typical ratios should be:**
- Conservative: 0.5x to 1.5x of FTE costs
- Realistic: 1.0x to 2.5x of FTE costs
- Aggressive: 2.0x to 3.0x of FTE costs

**Check these inputs:**
- Are your improvement percentages too optimistic?
- Are you double-counting benefits?
- Are your additional benefits (tool savings, etc.) realistic?"""
        
        red_flags.append({
            'type': 'Disproportionately High Benefits',
            'value': f"{currency_symbol}{total_annual_benefits:,.0f}",
            'reasoning': reasoning_text,
            'severity': 'medium'
        })
    
    # Red Flag 4: Extremely low FTE utilization
    if alert_fte_percentage > 0 and alert_fte_percentage < 0.1:
        reasoning_text = f"""Your alert workload only uses {alert_fte_percentage*100:.1f}% of the FTE time you've allocated for alerts.

**This suggests:**
- You may have allocated too much FTE time for this task
- Your alert triage time or volume may be underestimated

**Consider:** Is the **% of FTE Time on Alerts** input accurate?"""
        
        warnings.append({
            'type': 'Very Low Alert FTE Utilization',
            'value': f"{alert_fte_percentage*100:.1f}%",
            'reasoning': reasoning_text,
            'severity': 'low'
        })
    
    if incident_fte_percentage > 0 and incident_fte_percentage < 0.1:
        reasoning_text = f"""Your incident workload only uses {incident_fte_percentage*100:.1f}% of the FTE time you've allocated for incidents.

**This suggests:**
- You may have allocated too much FTE time for this task
- Your incident triage time or volume may be underestimated

**Consider:** Is the **% of FTE Time on Incidents** input accurate?"""
        
        warnings.append({
            'type': 'Very Low Incident FTE Utilization',
            'value': f"{incident_fte_percentage*100:.1f}%",
            'reasoning': reasoning_text,
            'severity': 'low'
        })
    
    # Red Flag 5: Unrealistic alert/incident ratios
    if alert_volume > 0 and incident_volume > 0:
        alert_to_incident_ratio = alert_volume / incident_volume
        if alert_to_incident_ratio < 2:
            reasoning_text = f"""Your alert-to-incident ratio is {alert_to_incident_ratio:.1f}:1, which is quite low.

**Typical ratios:**
- Well-tuned environments: 10:1 to 50:1
- Average environments: 5:1 to 20:1
- Noisy environments: 100:1 to 1000:1

**Your numbers:**
- Alerts: {alert_volume:,}
- Incidents: {incident_volume:,}

**This could indicate:**
- Your alert definition may actually be incidents
- Your environment is extremely well-tuned
- There may be a data collection issue"""
            
            warnings.append({
                'type': 'Unusual Alert-to-Incident Ratio',
                'value': f"{alert_to_incident_ratio:.1f}:1",
                'reasoning': reasoning_text,
                'severity': 'medium'
            })
    
    return red_flags, warnings

def show_calculation_reasoning_dashboard():
    """Display a comprehensive dashboard showing calculation reasoning"""
    st.subheader("🔍 Calculation Reasoning & Data Quality Dashboard")
    
    # Run red flag detection
    red_flags, warnings = detect_calculation_red_flags()
    
    # Display overall status
    if red_flags:
        st.error(f"⚠️ {len(red_flags)} critical issues detected that may indicate data problems")
    elif warnings:
        st.warning(f"⚠️ {len(warnings)} items to review")
    else:
        st.success("✅ All calculations appear reasonable")
    
    # Create tabs for different aspects
    reasoning_tabs = st.tabs(["🚨 Red Flags", "⚠️ Warnings", "🧮 Calculation Details", "📊 Data Quality Score"])
    
    with reasoning_tabs[0]:
        if red_flags:
            for flag in red_flags:
                if flag['severity'] == 'critical':
                    st.error(f"🔴 **{flag['type']}**: {flag['value']}")
                elif flag['severity'] == 'high':
                    st.error(f"🟠 **{flag['type']}**: {flag['value']}")
                else:
                    st.warning(f"🟡 **{flag['type']}**: {flag['value']}")
                
                with st.expander(f"See reasoning for {flag['type']}"):
                    st.markdown(flag['reasoning'])
        else:
            st.success("No red flags detected! Your calculations look reasonable.")
    
    with reasoning_tabs[1]:
        if warnings:
            for warning in warnings:
                st.warning(f"⚠️ **{warning['type']}**: {warning['value']}")
                with st.expander(f"See details for {warning['type']}"):
                    st.markdown(warning['reasoning'])
        else:
            st.info("No warnings - your inputs produce consistent calculations.")
    
    with reasoning_tabs[2]:
        show_detailed_calculation_breakdown()
    
    with reasoning_tabs[3]:
        show_data_quality_score(red_flags, warnings)

def show_detailed_calculation_breakdown():
    """Show step-by-step calculation breakdown"""
    st.markdown("### Step-by-Step Calculation Breakdown")
    
    # Get values from session state
    cost_per_alert = st.session_state.get('cost_per_alert', 0)
    cost_per_incident = st.session_state.get('cost_per_incident', 0)
    alert_volume = st.session_state.get('alert_volume', 0)
    incident_volume = st.session_state.get('incident_volume', 0)
    alert_ftes = st.session_state.get('alert_ftes', 0)
    incident_ftes = st.session_state.get('incident_ftes', 0)
    alert_fte_time_pct = st.session_state.get('alert_fte_time_pct', 100)
    incident_fte_time_pct = st.session_state.get('incident_fte_time_pct', 100)
    avg_alert_triage_time = st.session_state.get('avg_alert_triage_time', 0)
    avg_incident_triage_time = st.session_state.get('avg_incident_triage_time', 0)
    avg_alert_fte_salary = st.session_state.get('avg_alert_fte_salary', 0)
    avg_incident_fte_salary = st.session_state.get('avg_incident_fte_salary', 0)
    working_hours_per_fte_per_year = st.session_state.get('working_hours_per_fte_per_year', 2000)
    alert_fte_percentage = st.session_state.get('alert_fte_percentage', 0)
    incident_fte_percentage = st.session_state.get('incident_fte_percentage', 0)
    currency_symbol = st.session_state.get('currency', '$')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🚨 Alert Cost Calculation")
        if alert_volume > 0 and alert_ftes > 0:
            total_alert_time_hours = (alert_volume * avg_alert_triage_time) / 60
            allocated_fte_hours = alert_ftes * working_hours_per_fte_per_year * (alert_fte_time_pct / 100)
            total_fte_cost = alert_ftes * avg_alert_fte_salary
            cost_for_alerts = total_fte_cost * (alert_fte_time_pct / 100)
            
            st.markdown(f"""
**Step 1: Calculate total time needed for workload**
- {alert_volume:,} alerts × {avg_alert_triage_time} mins = {total_alert_time_hours:,.0f} hours/year

**Step 2: Calculate FTE capacity allocated to alerts**
- {alert_ftes} FTEs × {working_hours_per_fte_per_year:,.0f} hours × {alert_fte_time_pct}% = {allocated_fte_hours:,.0f} hours/year

**Step 3: Calculate utilization (of allocated time)**
- {total_alert_time_hours:,.0f} ÷ {allocated_fte_hours:,.0f} = {alert_fte_percentage:.1%}

**Step 4: Calculate cost allocation (based on your input)**
- Total FTE cost: {alert_ftes} × {currency_symbol}{avg_alert_fte_salary:,.0f} = {currency_symbol}{total_fte_cost:,.0f}
- Cost for alerts: {currency_symbol}{total_fte_cost:,.0f} × {alert_fte_time_pct}% = {currency_symbol}{cost_for_alerts:,.0f}

**Step 5: Cost per alert**
- {currency_symbol}{cost_for_alerts:,.0f} ÷ {alert_volume:,} = **{currency_symbol}{cost_per_alert:.2f}**
            """)
        else:
            st.info("No alert data provided")
    
    with col2:
        st.markdown("#### 🔧 Incident Cost Calculation")
        if incident_volume > 0 and incident_ftes > 0:
            total_incident_time_hours = (incident_volume * avg_incident_triage_time) / 60
            allocated_fte_hours = incident_ftes * working_hours_per_fte_per_year * (incident_fte_time_pct / 100)
            total_fte_cost = incident_ftes * avg_incident_fte_salary
            cost_for_incidents = total_fte_cost * (incident_fte_time_pct / 100)
            
            st.markdown(f"""
**Step 1: Calculate total time needed for workload**
- {incident_volume:,} incidents × {avg_incident_triage_time} mins = {total_incident_time_hours:,.0f} hours/year

**Step 2: Calculate FTE capacity allocated to incidents**
- {incident_ftes} FTEs × {working_hours_per_fte_per_year:,.0f} hours × {incident_fte_time_pct}% = {allocated_fte_hours:,.0f} hours/year

**Step 3: Calculate utilization (of allocated time)**
- {total_incident_time_hours:,.0f} ÷ {allocated_fte_hours:,.0f} = {incident_fte_percentage:.1%}

**Step 4: Calculate cost allocation (based on your input)**
- Total FTE cost: {incident_ftes} × {currency_symbol}{avg_incident_fte_salary:,.0f} = {currency_symbol}{total_fte_cost:,.0f}
- Cost for incidents: {currency_symbol}{total_fte_cost:,.0f} × {incident_fte_time_pct}% = {currency_symbol}{cost_for_incidents:,.0f}

**Step 5: Cost per incident**
- {currency_symbol}{cost_for_incidents:,.0f} ÷ {incident_volume:,} = **{currency_symbol}{cost_per_incident:.2f}**
            """)
        else:
            st.info("No incident data provided")

def show_data_quality_score(red_flags, warnings):
    """Calculate and display a data quality score"""
    st.markdown("### Data Quality Assessment")
    
    # Calculate quality score
    score = 100
    score -= len([f for f in red_flags if f['severity'] == 'critical']) * 30
    score -= len([f for f in red_flags if f['severity'] == 'high']) * 20
    score -= len([f for f in red_flags if f['severity'] == 'medium']) * 10
    score -= len(warnings) * 5
    score = max(0, score)
    
    # Display score with color coding
    if score >= 90:
        st.success(f"🟢 **Data Quality Score: {score}/100** - Excellent")
        st.markdown("Your inputs appear consistent and realistic.")
    elif score >= 70:
        st.warning(f"🟡 **Data Quality Score: {score}/100** - Good")
        st.markdown("Your inputs are mostly reasonable with some items to review.")
    elif score >= 50:
        st.error(f"🟠 **Data Quality Score: {score}/100** - Needs Review")
        st.markdown("Several calculation issues detected. Please review your inputs.")
    else:
        st.error(f"🔴 **Data Quality Score: {score}/100** - Poor")
        st.markdown("Major calculation issues detected. Data likely needs significant correction.")
    
    # Show recommendations
    if score < 90:
        st.markdown("#### 🎯 Recommendations to Improve Data Quality:")
        recommendations = []
        
        if any(f['type'] in ['Over-allocated Alert FTEs', 'Over-allocated Incident FTEs'] for f in red_flags):
            recommendations.append("• **Fix FTE over-allocation**: Increase FTE count or the '% of FTE Time' dedicated to the task")
        
        if any(f['type'] in ['High Cost Per Alert', 'High Cost Per Incident'] for f in red_flags):
            recommendations.append("• **Review cost calculations**: Check if '% of FTE Time', FTE counts, or salaries are realistic for the given volume")
        
        if any(f['type'] == 'Disproportionately High Benefits' for f in red_flags):
            recommendations.append("• **Validate benefit assumptions**: Ensure improvement percentages and additional benefits are conservative")
        
        if any(w['type'] in ['Very Low Alert FTE Utilization', 'Very Low Incident FTE Utilization'] for w in warnings):
            recommendations.append("• **Check FTE time allocation**: The workload is much lower than the time allocated; review the '% of FTE Time' input")
        
        for rec in recommendations:
            st.markdown(rec)

def show_enhanced_validation_section():
    """Enhanced validation section with detailed reasoning"""
    st.markdown("---")
    
    # Show the calculation reasoning dashboard
    show_calculation_reasoning_dashboard()
    
    # Add quick fix suggestions
    red_flags, warnings = detect_calculation_red_flags()
    if red_flags or warnings:
        with st.expander("🔧 Quick Fix Suggestions"):
            if any(f['type'] in ['Over-allocated Alert FTEs', 'Over-allocated Incident FTEs'] for f in red_flags):
                st.markdown("""
**For FTE over-allocation issues:**
1. Increase the **% of FTE time** dedicated to the task.
2. Increase the number of FTEs assigned.
3. Verify triage time and volume estimates are correct.
                """)
            
            if any(f['type'] in ['High Cost Per Alert', 'High Cost Per Incident'] for f in red_flags):
                st.markdown("""
**For high cost per alert/incident:**
1. Check if the **% of FTE time** is realistic for the given volume.
2. Confirm FTE salaries include only base salary + benefits.
3. Ensure volumes are annual figures, not monthly/quarterly.
                """)
            
            if any(f['type'] == 'Disproportionately High Benefits' for f in red_flags):
                st.markdown("""
**For overly optimistic benefits:**
1. Use conservative improvement percentages (20-40% rather than 60-80%).
2. Avoid double-counting benefits across categories.
3. Validate additional benefits with concrete business cases.
                """)

# --- MONTE CARLO SIMULATION FUNCTIONS ---

def run_monte_carlo_simulation(n_simulations=1000):
    """Run Monte Carlo simulation for ROI uncertainty analysis"""
    # Get current values from session state
    alert_reduction_pct = st.session_state.get('alert_reduction_pct', 0)
    incident_reduction_pct = st.session_state.get('incident_reduction_pct', 0)
    mttr_improvement_pct = st.session_state.get('mttr_improvement_pct', 0)
    implementation_delay_months = st.session_state.get('implementation_delay', 6)
    platform_cost = st.session_state.get('platform_cost', 0)
    services_cost = st.session_state.get('services_cost', 0)
    evaluation_years = st.session_state.get('evaluation_years', 3)
    discount_rate = st.session_state.get('discount_rate', 10) / 100
    
    # Get other required values
    alert_volume = st.session_state.get('alert_volume', 0)
    incident_volume = st.session_state.get('incident_volume', 0)
    major_incident_volume = st.session_state.get('major_incident_volume', 0)
    cost_per_alert = st.session_state.get('cost_per_alert', 0)
    cost_per_incident = st.session_state.get('cost_per_incident', 0)
    avg_mttr_hours = st.session_state.get('avg_mttr_hours', 0)
    avg_major_incident_cost = st.session_state.get('avg_major_incident_cost', 0)
    tool_savings = st.session_state.get('tool_savings', 0)
    people_cost_per_year = st.session_state.get('people_efficiency', 0)
    fte_avoidance = st.session_state.get('fte_avoidance', 0)
    sla_penalty_avoidance = st.session_state.get('sla_penalty', 0)
    revenue_growth = st.session_state.get('revenue_growth', 0)
    capex_savings = st.session_state.get('capex_savings', 0)
    opex_savings = st.session_state.get('opex_savings', 0)
    benefits_ramp_up_months = st.session_state.get('benefits_ramp_up', 3)
    
    np.random.seed(42)  # For reproducible results
    roi_results = []
    npv_results = []
    
    for _ in range(n_simulations):
        # Add random variation to key inputs (assuming normal distribution with std dev = 20% of mean)
        sim_alert_reduction = max(0, min(100, np.random.normal(alert_reduction_pct, alert_reduction_pct * 0.2)))
        sim_incident_reduction = max(0, min(100, np.random.normal(incident_reduction_pct, incident_reduction_pct * 0.2)))
        sim_mttr_improvement = max(0, min(100, np.random.normal(mttr_improvement_pct, mttr_improvement_pct * 0.2)))
        sim_implementation_delay = max(1, np.random.normal(implementation_delay_months, implementation_delay_months * 0.15))
        sim_platform_cost = max(0, np.random.normal(platform_cost, platform_cost * 0.1))
        sim_services_cost = max(0, np.random.normal(services_cost, services_cost * 0.15))
        
        # Calculate benefits with simulated values
        sim_alert_savings = (alert_volume * sim_alert_reduction / 100) * cost_per_alert
        sim_incident_savings = (incident_volume * sim_incident_reduction / 100) * cost_per_incident
        sim_mttr_savings = major_incident_volume * (sim_mttr_improvement / 100) * avg_mttr_hours * avg_major_incident_cost
        
        sim_total_benefits = (sim_alert_savings + sim_incident_savings + sim_mttr_savings + 
                             tool_savings + people_cost_per_year + fte_avoidance + 
                             sla_penalty_avoidance + revenue_growth + capex_savings + opex_savings)
        
        # Calculate NPV with simulated values (simplified)
        sim_cash_flows = []
        for year in range(1, evaluation_years + 1):
            year_benefits = sim_total_benefits
            year_platform_cost = sim_platform_cost
            year_services_cost = sim_services_cost if year == 1 else 0
            year_net_cash_flow = year_benefits - year_platform_cost - year_services_cost
            sim_cash_flows.append(year_net_cash_flow)
        
        sim_npv = sum([cf / ((1 + discount_rate) ** (i+1)) for i, cf in enumerate(sim_cash_flows)])
        sim_total_costs = sim_platform_cost * evaluation_years + sim_services_cost
        sim_roi = (sim_npv / sim_total_costs * 100) if sim_total_costs > 0 else 0
        
        roi_results.append(sim_roi)
        npv_results.append(sim_npv)
    
    return roi_results, npv_results

def calculate_break_even_scenarios():
    """Calculate various break-even scenarios"""
    break_even_scenarios = {}
    
    platform_cost = st.session_state.get('platform_cost', 0)
    services_cost = st.session_state.get('services_cost', 0)
    evaluation_years = st.session_state.get('evaluation_years', 3)
    alert_volume = st.session_state.get('alert_volume', 0)
    incident_volume = st.session_state.get('incident_volume', 0)
    major_incident_volume = st.session_state.get('major_incident_volume', 0)
    cost_per_alert = st.session_state.get('cost_per_alert', 0)
    cost_per_incident = st.session_state.get('cost_per_incident', 0)
    avg_mttr_hours = st.session_state.get('avg_mttr_hours', 0)
    avg_major_incident_cost = st.session_state.get('avg_major_incident_cost', 0)
    
    total_costs_annual = platform_cost + (services_cost / evaluation_years)
    
    # Break-even alert reduction percentage
    if cost_per_alert > 0 and alert_volume > 0:
        required_alert_reduction = (total_costs_annual / (alert_volume * cost_per_alert)) * 100
        break_even_scenarios['Alert Reduction'] = min(required_alert_reduction, 100)
    
    # Break-even incident reduction percentage
    if cost_per_incident > 0 and incident_volume > 0:
        required_incident_reduction = (total_costs_annual / (incident_volume * cost_per_incident)) * 100
        break_even_scenarios['Incident Reduction'] = min(required_incident_reduction, 100)
    
    # Break-even MTTR improvement
    if avg_major_incident_cost > 0 and major_incident_volume > 0 and avg_mttr_hours > 0:
        required_mttr_improvement = (total_costs_annual / (major_incident_volume * avg_mttr_hours * avg_major_incident_cost)) * 100
        break_even_scenarios['MTTR Improvement'] = min(required_mttr_improvement, 100)
    
    return break_even_scenarios

# --- ENHANCED VISUALIZATION FUNCTIONS ---

def create_before_after_comparison():
    """Show before/after operational metrics"""
    # Get values from session state
    alert_volume = st.session_state.get('alert_volume', 0)
    incident_volume = st.session_state.get('incident_volume', 0)
    major_incident_volume = st.session_state.get('major_incident_volume', 0)
    avg_mttr_hours = st.session_state.get('avg_mttr_hours', 0)
    mttr_improvement_pct = st.session_state.get('mttr_improvement_pct', 0)
    currency_symbol = st.session_state.get('currency', '$')
    
    # Get calculated savings from session state
    alert_reduction_savings = st.session_state.get('alert_reduction_savings', 0)
    alert_triage_savings = st.session_state.get('alert_triage_savings', 0)
    incident_reduction_savings = st.session_state.get('incident_reduction_savings', 0)
    incident_triage_savings = st.session_state.get('incident_triage_savings', 0)
    major_incident_savings = st.session_state.get('major_incident_savings', 0)
    
    # Calculate remaining values
    remaining_alerts = alert_volume * (1 - st.session_state.get('alert_reduction_pct', 0) / 100)
    remaining_incidents = incident_volume * (1 - st.session_state.get('incident_reduction_pct', 0) / 100)
    
    # Calculate total savings for each category
    total_alert_savings = alert_reduction_savings + alert_triage_savings
    total_incident_savings = incident_reduction_savings + incident_triage_savings
    
    comparison_data = {
        'Metric': [
            'Alerts/Year',
            'Incidents/Year', 
            'Major Incidents/Year',
            'Avg MTTR (hours)',
        ],
        'Current State': [
            f"{alert_volume:,}",
            f"{incident_volume:,}",
            f"{major_incident_volume:,}",
            f"{avg_mttr_hours:.1f}",
        ],
        'Future State': [
            f"{remaining_alerts:,.0f}",
            f"{remaining_incidents:,.0f}",
            f"{major_incident_volume:,}",  # Major incidents don't reduce, just MTTR improves
            f"{avg_mttr_hours * (1 - mttr_improvement_pct/100):.1f}",
        ],
        'Annual Savings': [
            f"{currency_symbol}{total_alert_savings:,.0f}",
            f"{currency_symbol}{total_incident_savings:,.0f}",
            f"{currency_symbol}{major_incident_savings:,.0f}",
            f"{currency_symbol}{major_incident_savings:,.0f}",  # MTTR savings shown here too
        ]
    }
    
    return pd.DataFrame(comparison_data)

def create_benefit_breakdown_chart(currency_symbol):
    """Create a detailed breakdown of benefits by category"""
    
    # Get benefit values from session state
    alert_reduction_savings = st.session_state.get('alert_reduction_savings', 0)
    alert_triage_savings = st.session_state.get('alert_triage_savings', 0)
    incident_reduction_savings = st.session_state.get('incident_reduction_savings', 0)
    incident_triage_savings = st.session_state.get('incident_triage_savings', 0)
    major_incident_savings = st.session_state.get('major_incident_savings', 0)
    tool_savings = st.session_state.get('tool_savings', 0)
    people_cost_per_year = st.session_state.get('people_efficiency', 0)
    fte_avoidance = st.session_state.get('fte_avoidance', 0)
    sla_penalty_avoidance = st.session_state.get('sla_penalty', 0)
    revenue_growth = st.session_state.get('revenue_growth', 0)
    capex_savings = st.session_state.get('capex_savings', 0)
    opex_savings = st.session_state.get('opex_savings', 0)
    # Asset management benefits (no CMDB)
    asset_discovery_savings = st.session_state.get('asset_discovery_savings', 0)
    
    benefits_data = {
        'Category': [
            'Alert Reduction', 'Alert Triage Efficiency', 'Incident Reduction', 
            'Incident Triage Efficiency', 'MTTR Improvement', 'Tool Consolidation',
            'People Efficiency', 'FTE Avoidance', 'SLA Penalty Avoidance',
            'Revenue Growth', 'CAPEX Savings', 'OPEX Savings',
            'Asset Discovery Automation'
        ],
        'Annual Value': [
            alert_reduction_savings, alert_triage_savings, incident_reduction_savings,
            incident_triage_savings, major_incident_savings, tool_savings,
            people_cost_per_year, fte_avoidance, sla_penalty_avoidance,
            revenue_growth, capex_savings, opex_savings,
            asset_discovery_savings
        ],
        'Category Type': [
            'Operational', 'Operational', 'Operational', 'Operational', 'Operational',
            'Cost Reduction', 'Efficiency', 'Strategic', 'Risk Mitigation',
            'Revenue', 'Cost Reduction', 'Cost Reduction',
            'Asset Management'
        ]
    }
    
    df = pd.DataFrame(benefits_data)
    df = df[df['Annual Value'] > 0]  # Only show categories with value
    
    if len(df) == 0:
        return None
    
    fig = px.bar(df, x='Annual Value', y='Category', color='Category Type',
                 title='Annual Benefits Breakdown by Category',
                 labels={'Annual Value': f'Annual Value ({currency_symbol})', 'Category': 'Benefit Category'},
                 orientation='h')
    
    fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
    
    return fig

def create_cost_vs_benefit_waterfall(currency_symbol):
    """Create a waterfall chart showing cost vs benefits"""
    
    # Get values from session state
    alert_reduction_savings = st.session_state.get('alert_reduction_savings', 0)
    alert_triage_savings = st.session_state.get('alert_triage_savings', 0)
    incident_reduction_savings = st.session_state.get('incident_reduction_savings', 0)
    incident_triage_savings = st.session_state.get('incident_triage_savings', 0)
    major_incident_savings = st.session_state.get('major_incident_savings', 0)
    tool_savings = st.session_state.get('tool_savings', 0)
    people_cost_per_year = st.session_state.get('people_efficiency', 0)
    fte_avoidance = st.session_state.get('fte_avoidance', 0)
    sla_penalty_avoidance = st.session_state.get('sla_penalty', 0)
    revenue_growth = st.session_state.get('revenue_growth', 0)
    capex_savings = st.session_state.get('capex_savings', 0)
    opex_savings = st.session_state.get('opex_savings', 0)
    platform_cost = st.session_state.get('platform_cost', 0)
    services_cost = st.session_state.get('services_cost', 0)
    # Asset management savings (no CMDB)
    asset_discovery_savings = st.session_state.get('asset_discovery_savings', 0)
    
    # Prepare data for waterfall chart
    categories = ['Starting Point', 'Alert Savings', 'Incident Savings', 'MTTR Savings', 
                 'Asset Management Savings', 'Additional Benefits', 'Platform Cost', 'Services Cost', 'Net Position']
    
    values = [0, 
             alert_reduction_savings + alert_triage_savings,
             incident_reduction_savings + incident_triage_savings,
             major_incident_savings,
             asset_discovery_savings,
             tool_savings + people_cost_per_year + fte_avoidance + sla_penalty_avoidance + revenue_growth + capex_savings + opex_savings,
             -platform_cost,
             -services_cost,
             0]  # Will be calculated
    
    # Calculate cumulative for net position
    values[-1] = sum(values[1:-1])
    
    fig = go.Figure(go.Waterfall(
        name="Annual Impact",
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "relative", "relative", "relative", "relative", "total"],
        x=categories,
        y=values,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        text=[f"{currency_symbol}{v:,.0f}" for v in values],
        textposition="outside"
    ))
    
    fig.update_layout(
        title="Annual Cost vs Benefits Waterfall Analysis",
        showlegend=False,
        height=500,
        yaxis_title=f"Value ({currency_symbol})"
    )
    
    return fig

def create_roi_comparison_chart(scenario_results, currency_symbol):
    """Create ROI comparison across scenarios with confidence intervals"""
    
    scenarios_list = list(scenario_results.keys())
    rois = [scenario_results[scenario]['roi'] * 100 for scenario in scenarios_list]
    npvs = [scenario_results[scenario]['npv'] for scenario in scenarios_list]
    colors_list = [scenario_results[scenario]['color'] for scenario in scenarios_list]
    
    # Create subplot with secondary y-axis
    fig = go.Figure()
    
    # Add ROI bars
    fig.add_trace(go.Bar(
        name='ROI (%)',
        x=scenarios_list,
        y=rois,
        marker_color=colors_list,
        text=[f'{roi:.1f}%' for roi in rois],
        textposition='outside',
        yaxis='y'
    ))
    
    # Add NPV line
    fig.add_trace(go.Scatter(
        name='NPV',
        x=scenarios_list,
        y=npvs,
        mode='lines+markers',
        line=dict(color='black', width=3),
        marker=dict(size=10),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title='ROI and NPV Comparison Across Scenarios',
        xaxis_title='Scenario',
        yaxis=dict(title='ROI (%)', side='left'),
        yaxis2=dict(title=f'NPV ({currency_symbol})', side='right', overlaying='y'),
        height=400
    )
    
    return fig

# --- EXPORT/IMPORT FUNCTIONS ---

def get_all_input_values():
    """Collect all input values from the current session state"""
    input_values = {}
    
    # Get all the input keys from your existing inputs (removed compliance fields)
    input_keys = [
        # Basic Configuration
        'solution_name', 'industry_template', 'currency', 
        
        # Implementation Timeline
        'implementation_delay', 'benefits_ramp_up', 'billing_start_month',
        
        # Working Hours Configuration
        'hours_per_day', 'days_per_week', 'weeks_per_year', 'holiday_sick_days',
        
        # Alert Management
        'alert_volume', 'alert_ftes', 'alert_fte_time_pct', 'avg_alert_triage_time', 'avg_alert_fte_salary',
        'alert_reduction_pct', 'alert_triage_time_saved_pct',
        
        # Incident Management
        'incident_volume', 'incident_ftes', 'incident_fte_time_pct', 'avg_incident_triage_time', 'avg_incident_fte_salary',
        'incident_reduction_pct', 'incident_triage_time_savings_pct',
        
        # Major Incidents
        'major_incident_volume', 'avg_major_incident_cost', 'avg_mttr_hours', 'mttr_improvement_pct',
        
        # Asset Discovery (no CMDB)
        'asset_volume', 'manual_discovery_cycles_per_year', 'hours_per_discovery_cycle',
        'asset_management_ftes', 'asset_mgmt_fte_time_pct', 'avg_asset_mgmt_fte_salary', 'asset_discovery_automation_pct',
        
        # Additional Benefits
        'tool_savings', 'people_efficiency', 'fte_avoidance', 'sla_penalty', 
        'revenue_growth', 'capex_savings', 'opex_savings',
        
        # Costs
        'platform_cost', 'services_cost',
        
        # Financial Settings
        'evaluation_years', 'discount_rate'
    ]
    
    # Collect values from session state
    for key in input_keys:
        if key in st.session_state:
            input_values[key] = st.session_state[key]
        else:
            # Fallback to default values if not in session state
            input_values[key] = get_default_value(key)
    
    return input_values

def get_default_value(key):
    """Get default values for inputs"""
    defaults = {
        'solution_name': 'AIOPs',
        'industry_template': 'Custom',
        'currency': '$',
        'implementation_delay': 6,
        'benefits_ramp_up': 3,
        'billing_start_month': 1,
        'hours_per_day': 8.0,
        'days_per_week': 5,
        'weeks_per_year': 52,
        'holiday_sick_days': 25,
        'alert_volume': 0,
        'alert_ftes': 0,
        'alert_fte_time_pct': 100,
        'avg_alert_triage_time': 0,
        'avg_alert_fte_salary': 0,
        'alert_reduction_pct': 0,
        'alert_triage_time_saved_pct': 0,
        'incident_volume': 0,
        'incident_ftes': 0,
        'incident_fte_time_pct': 100,
        'avg_incident_triage_time': 0,
        'avg_incident_fte_salary': 0,
        'incident_reduction_pct': 0,
        'incident_triage_time_savings_pct': 0,
        'major_incident_volume': 0,
        'avg_major_incident_cost': 0,
        'avg_mttr_hours': 0.0,
        'mttr_improvement_pct': 0,
        # Asset management defaults (no CMDB)
        'asset_volume': 0,
        'manual_discovery_cycles_per_year': 0,
        'hours_per_discovery_cycle': 0,
        'asset_management_ftes': 0,
        'asset_mgmt_fte_time_pct': 100,
        'avg_asset_mgmt_fte_salary': 0,
        'asset_discovery_automation_pct': 0,
        'tool_savings': 0,
        'people_efficiency': 0,
        'fte_avoidance': 0,
        'sla_penalty': 0,
        'revenue_growth': 0,
        'capex_savings': 0,
        'opex_savings': 0,
        'platform_cost': 0,
        'services_cost': 0,
        'evaluation_years': 3,
        'discount_rate': 10
    }
    return defaults.get(key, 0)

def export_to_csv(input_values):
    """Export input values to CSV format"""
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Parameter', 'Value', 'Description'])
    
    # Define parameter descriptions for better readability (removed compliance descriptions)
    descriptions = {
        'solution_name': 'Customer Name',
        'industry_template': 'Industry Template',
        'currency': 'Currency Symbol',
        'implementation_delay': 'Implementation Delay (months)',
        'benefits_ramp_up': 'Benefits Ramp-up Period (months)',
        'billing_start_month': 'Billing Start Month',
        'hours_per_day': 'Working Hours per Day',
        'days_per_week': 'Working Days per Week',
        'weeks_per_year': 'Working Weeks per Year',
        'holiday_sick_days': 'Holiday + Sick Days per Year',
        'alert_volume': 'Total Infrastructure Related Alerts per Year',
        'alert_ftes': 'Total FTEs Managing Infrastructure Alerts',
        'alert_fte_time_pct': '% of FTE Time on Alerts',
        'avg_alert_triage_time': 'Average Alert Triage Time (minutes)',
        'avg_alert_fte_salary': 'Average Annual Salary per Alert Management FTE',
        'alert_reduction_pct': '% Alert Reduction',
        'alert_triage_time_saved_pct': '% Alert Triage Time Reduction',
        'incident_volume': 'Total Infrastructure Related Incident Volumes per Year',
        'incident_ftes': 'Total FTEs Managing Infrastructure Incidents',
        'incident_fte_time_pct': '% of FTE Time on Incidents',
        'avg_incident_triage_time': 'Average Incident Triage Time (minutes)',
        'avg_incident_fte_salary': 'Average Annual Salary per Incident Management FTE',
        'incident_reduction_pct': '% Incident Reduction',
        'incident_triage_time_savings_pct': '% Incident Triage Time Reduction',
        'major_incident_volume': 'Total Infrastructure Related Major Incidents per Year (Sev1)',
        'avg_major_incident_cost': 'Average Major Incident Cost per Hour',
        'avg_mttr_hours': 'Average MTTR (hours)',
        'mttr_improvement_pct': 'MTTR Improvement Percentage',
        # Asset management descriptions (no CMDB)
        'asset_volume': 'Total IT Assets Under Management',
        'manual_discovery_cycles_per_year': 'Manual Discovery Cycles per Year',
        'hours_per_discovery_cycle': 'Hours per Manual Discovery Cycle',
        'asset_management_ftes': 'Total FTEs Managing IT Assets',
        'asset_mgmt_fte_time_pct': '% of FTE Time on Asset Discovery',
        'avg_asset_mgmt_fte_salary': 'Average Annual Salary per Asset Management FTE',
        'asset_discovery_automation_pct': '% Asset Discovery Process Automated',
        'tool_savings': 'Tool Consolidation Savings',
        'people_efficiency': 'People Efficiency Gains',
        'fte_avoidance': 'FTE Avoidance (annualized value)',
        'sla_penalty': 'SLA Penalty Avoidance',
        'revenue_growth': 'Revenue Growth',
        'capex_savings': 'Capital Expenditure Savings',
        'opex_savings': 'Operational Expenditure Savings',
        'platform_cost': 'Annual Subscription Cost',
        'services_cost': 'Implementation & Services (One-Time)',
        'evaluation_years': 'Evaluation Period (Years)',
        'discount_rate': 'NPV Discount Rate (%)'
    }
    
    # Write data rows
    for key, value in input_values.items():
        description = descriptions.get(key, key.replace('_', ' ').title())
        writer.writerow([key, value, description])
    
    return output.getvalue()

def import_from_csv(csv_content):
    """Import input values from CSV content and update session state"""
    try:
        # Parse CSV content
        reader = csv.DictReader(StringIO(csv_content))
        imported_values = {}
        
        for row in reader:
            key = row['Parameter']
            value = row['Value']
            
            # Convert value to appropriate type
            try:
                # Try to convert to number first
                if '.' in str(value):
                    value = float(value)
                else:
                    value = int(value)
            except (ValueError, TypeError):
                # Keep as string if not a number
                value = str(value)
            
            imported_values[key] = value
        
        # Update session state with imported values
        for key, value in imported_values.items():
            st.session_state[key] = value
        
        return True, f"Successfully imported {len(imported_values)} parameters"
    
    except Exception as e:
        return False, f"Error importing CSV: {str(e)}"

def export_to_json(input_values):
    """Export input values to JSON format"""
    # Add metadata
    export_data = {
        'metadata': {
            'export_date': datetime.now().isoformat(),
            'version': '2.3',
            'tool': 'Enhanced BVA Business Value Assessment with Calculation Reasoning'
        },
        'configuration': input_values
    }
    return json.dumps(export_data, indent=2)

def import_from_json(json_content):
    """Import input values from JSON content and update session state"""
    try:
        data = json.loads(json_content)
        
        # Extract configuration data
        if 'configuration' in data:
            imported_values = data['configuration']
        else:
            # Assume the entire JSON is the configuration
            imported_values = data
        
        # Update session state with imported values
        for key, value in imported_values.items():
            st.session_state[key] = value
        
        return True, f"Successfully imported {len(imported_values)} parameters"
    
    except Exception as e:
        return False, f"Error importing JSON: {str(e)}"

# --- Enhanced PDF Executive Summary Functions ---

def generate_executive_pdf_report(logo_file=None):
    """Generate a comprehensive PDF executive summary report"""
    if not REPORT_DEPENDENCIES_AVAILABLE:
        return None, "PDF generation requires additional dependencies (reportlab, matplotlib)"
    
    try:
        # Get current values from session state with proper defaults
        solution_name = st.session_state.get('solution_name', 'AIOPs')
        currency_symbol = st.session_state.get('currency', '$')
        evaluation_years = st.session_state.get('evaluation_years', 3)
        billing_start_month = st.session_state.get('billing_start_month', 1)
        implementation_delay_months = st.session_state.get('implementation_delay', 6)
        benefits_ramp_up_months = st.session_state.get('benefits_ramp_up', 3)
        discount_rate = st.session_state.get('discount_rate', 10) / 100
        
        # Get input values with defaults
        alert_volume = st.session_state.get('alert_volume', 0)
        incident_volume = st.session_state.get('incident_volume', 0)
        major_incident_volume = st.session_state.get('major_incident_volume', 0)
        alert_reduction_pct = st.session_state.get('alert_reduction_pct', 0)
        incident_reduction_pct = st.session_state.get('incident_reduction_pct', 0)
        mttr_improvement_pct = st.session_state.get('mttr_improvement_pct', 0)
        
        # Calculate working hours
        hours_per_day = st.session_state.get('hours_per_day', 8.0)
        days_per_week = st.session_state.get('days_per_week', 5)
        weeks_per_year = st.session_state.get('weeks_per_year', 52)
        holiday_sick_days = st.session_state.get('holiday_sick_days', 25)
        working_hours_fte_year = ((weeks_per_year * days_per_week) - holiday_sick_days) * hours_per_day
        
        # Get costs
        platform_cost = st.session_state.get('platform_cost', 0)
        services_cost = st.session_state.get('services_cost', 0)
        
        # Get calculated benefits from session state
        total_annual_benefits = st.session_state.get('total_annual_benefits', 0)
        alert_reduction_savings = st.session_state.get('alert_reduction_savings', 0)
        incident_reduction_savings = st.session_state.get('incident_reduction_savings', 0)
        major_incident_savings = st.session_state.get('major_incident_savings', 0)
        alert_triage_savings = st.session_state.get('alert_triage_savings', 0)
        incident_triage_savings = st.session_state.get('incident_triage_savings', 0)
        tool_savings = st.session_state.get('tool_savings', 0)
        people_efficiency = st.session_state.get('people_efficiency', 0)
        fte_avoidance = st.session_state.get('fte_avoidance', 0)
        other_benefits = (st.session_state.get('sla_penalty', 0) + 
                         st.session_state.get('revenue_growth', 0) + 
                         st.session_state.get('capex_savings', 0) + 
                         st.session_state.get('opex_savings', 0))
        equivalent_ftes = st.session_state.get('equivalent_ftes_from_savings', 0)
        operational_savings = st.session_state.get('total_operational_savings_from_time_saved', 0)
        # Asset management benefits (no CMDB)
        asset_discovery_savings = st.session_state.get('asset_discovery_savings', 0)
        
        # Get scenario results from session state
        scenario_results_from_state = st.session_state.get('scenario_results', None)
        if scenario_results_from_state:
            scenario_results = scenario_results_from_state
        else:
            # Create basic scenario results if not available
            total_investment = platform_cost * evaluation_years + services_cost
            basic_npv = total_annual_benefits * evaluation_years - total_investment
            basic_roi = (basic_npv / total_investment) if total_investment > 0 else 0
            
            scenario_results = {
                'Expected': {
                    'npv': basic_npv,
                    'roi': basic_roi,
                    'payback_months': '12 months',
                    'description': 'Baseline assumptions as entered'
                },
                'Conservative': {
                    'npv': basic_npv * 0.7,
                    'roi': basic_roi * 0.7,
                    'payback_months': '18 months',
                    'description': 'Benefits 30% lower, implementation 30% longer'
                },
                'Optimistic': {
                    'npv': basic_npv * 1.2,
                    'roi': basic_roi * 1.2,
                    'payback_months': '9 months',
                    'description': 'Benefits 20% higher, implementation 20% faster'
                }
            }
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, 
                               topMargin=72, bottomMargin=18)
        elements = []
        styles = getSampleStyleSheet()
        
        # Define custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.darkblue,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.darkblue,
            spaceBefore=20,
            spaceAfter=12
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=12,
            alignment=TA_JUSTIFY
        )
        
        # Add logo if provided
        if logo_file is not None:
            try:
                logo_file.seek(0)  # Reset file pointer
                logo_image = Image(logo_file, width=3*inch, height=1.5*inch)
                logo_image.hAlign = 'CENTER'
                elements.append(logo_image)
                elements.append(Spacer(1, 20))
            except Exception:
                # Logo placeholder if fails
                logo_placeholder = Paragraph("Company Logo", 
                    ParagraphStyle('LogoPlaceholder', parent=styles['Normal'], 
                                 fontSize=12, alignment=TA_CENTER, textColor=colors.grey))
                elements.append(logo_placeholder)
                elements.append(Spacer(1, 20))
        
        # Title
        elements.append(Paragraph("Business Value Assessment Report", title_style))
        elements.append(Paragraph(f"{solution_name} Implementation", title_style))
        elements.append(Spacer(1, 30))
        
        # Executive Summary
        elements.append(Paragraph("Executive Summary", heading_style))
        
        expected_result = scenario_results['Expected']
        total_asset_savings = asset_discovery_savings
        exec_summary = f"""
        This comprehensive business value assessment analyzes the financial impact of implementing {solution_name} 
        over a {evaluation_years}-year period. Our analysis shows a projected NPV of {currency_symbol}{expected_result['npv']:,.0f} 
        with an ROI of {expected_result['roi']*100:.1f}%. The payback period is estimated at {expected_result['payback_months']}.
        
        <br/><br/>
        The implementation will process {alert_volume:,} alerts and {incident_volume:,} incidents annually, with projected 
        reductions of {alert_reduction_pct}% and {incident_reduction_pct}% respectively. Major incident MTTR improvements of 
        {mttr_improvement_pct}% will deliver significant operational benefits.
        
        <br/><br/>
        <b>Asset Discovery Value:</b> The solution will also automate asset discovery processes, 
        delivering an additional {currency_symbol}{total_asset_savings:,.0f} in annual value through improved IT asset management.
        
        <br/><br/>
        <b>Key Recommendation:</b> Proceed with implementation based on strong financial justification and strategic benefits.
        """
        elements.append(Paragraph(exec_summary, body_style))
        elements.append(Spacer(1, 20))
        
        # Key Financial Metrics
        elements.append(Paragraph("Key Financial Metrics", heading_style))
        
        total_investment = platform_cost * evaluation_years + services_cost
        metrics_data = [
            ['Metric', 'Value', 'Description'],
            ['Net Present Value (NPV)', f'{currency_symbol}{expected_result["npv"]:,.0f}', 'Total value in current dollars'],
            ['Return on Investment (ROI)', f'{expected_result["roi"]*100:.1f}%', 'Percentage return over investment'],
            ['Payback Period', f'{expected_result["payback_months"]}', 'Time to recover initial investment'],
            ['Total Annual Benefits', f'{currency_symbol}{total_annual_benefits:,.0f}', 'Expected yearly value creation'],
            ['Total Investment', f'{currency_symbol}{total_investment:,.0f}', 'Total cost over evaluation period'],
            ['Equivalent FTEs Gained', f'{equivalent_ftes:.1f} FTEs', 'Strategic capacity from savings']
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2.2*inch, 1.8*inch, 2.5*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 20))
        
        # Scenario Analysis
        elements.append(Paragraph("Scenario Analysis", heading_style))
        
        scenario_data = [['Scenario', 'NPV', 'ROI', 'Payback', 'Description']]
        for name, result in scenario_results.items():
            scenario_data.append([
                name,
                f'{currency_symbol}{result["npv"]:,.0f}',
                f'{result["roi"]*100:.1f}%',
                result["payback_months"],
                result["description"]
            ])
        
        scenario_table = Table(scenario_data, colWidths=[1*inch, 1.2*inch, 0.8*inch, 1*inch, 2.5*inch])
        scenario_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(scenario_table)
        elements.append(Spacer(1, 20))
        
        # Benefits Breakdown
        elements.append(Paragraph("Annual Benefits Breakdown", heading_style))
        
        benefits_data = [['Benefit Category', 'Annual Value', 'Percentage']]
        benefit_categories = [
            ('Alert Reduction Savings', alert_reduction_savings),
            ('Alert Triage Efficiency', alert_triage_savings),
            ('Incident Reduction Savings', incident_reduction_savings),
            ('Incident Triage Efficiency', incident_triage_savings),
            ('MTTR Improvement', major_incident_savings),
            ('Asset Discovery Automation', asset_discovery_savings),
            ('Tool Consolidation', tool_savings),
            ('People Efficiency', people_efficiency),
            ('FTE Avoidance', fte_avoidance),
            ('Other Benefits', other_benefits)
        ]
        
        for category, value in benefit_categories:
            if value > 0:
                percentage = (value / total_annual_benefits * 100) if total_annual_benefits > 0 else 0
                benefits_data.append([category, f'{currency_symbol}{value:,.0f}', f'{percentage:.1f}%'])
        
        if len(benefits_data) == 1:
            benefits_data.append(['Total Benefits', f'{currency_symbol}{total_annual_benefits:,.0f}', '100.0%'])
        
        benefits_table = Table(benefits_data, colWidths=[3*inch, 1.5*inch, 1*inch])
        benefits_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(benefits_table)
        elements.append(Spacer(1, 20))
        
        # Footer
        footer_text = f"Report generated on {datetime.now().strftime('%B %d, %Y')} using Enhanced Business Value Assessment Tool v2.3"
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        elements.append(Paragraph(footer_text, footer_style))
        
        # Build PDF
        doc.build(elements)
        
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data, None
        
    except Exception as e:
        return None, f"Error generating PDF: {str(e)}"

# --- CALCULATION FUNCTIONS ---

def calculate_alert_costs(alert_volume, alert_ftes, avg_alert_triage_time, avg_salary_per_year, 
                         hours_per_day, days_per_week, weeks_per_year, holiday_sick_days,
                         alert_fte_time_pct):
    """Calculate the true cost per alert based on FTE time allocation"""
    if alert_volume == 0 or alert_ftes == 0:
        return 0, 0, 0, 0
    
    # Calculate total time required by the workload
    total_alert_time_minutes_per_year = alert_volume * avg_alert_triage_time
    total_alert_time_hours_per_year = total_alert_time_minutes_per_year / 60
    
    # Calculate total available hours from the FTE pool
    total_working_days = (weeks_per_year * days_per_week) - holiday_sick_days
    working_hours_per_fte_per_year = total_working_days * hours_per_day
    total_available_fte_hours = alert_ftes * working_hours_per_fte_per_year
    
    # 1. Calculate the portion of FTE hours ALLOCATED to alerts
    total_allocated_fte_hours = total_available_fte_hours * (alert_fte_time_pct / 100.0)

    # 2. Calculate utilization WITHIN the allocated time (for validation)
    utilization_of_allocated_time = total_alert_time_hours_per_year / total_allocated_fte_hours if total_allocated_fte_hours > 0 else 0
    
    # 3. Calculate cost based on the user-defined percentage
    total_fte_cost = alert_ftes * avg_salary_per_year
    total_alert_handling_cost = total_fte_cost * (alert_fte_time_pct / 100.0)
    
    cost_per_alert = total_alert_handling_cost / alert_volume if alert_volume > 0 else 0
    
    # Return the new utilization metric for the red flag system
    return cost_per_alert, total_alert_handling_cost, utilization_of_allocated_time, working_hours_per_fte_per_year

def calculate_incident_costs(incident_volume, incident_ftes, avg_incident_triage_time, avg_salary_per_year,
                           hours_per_day, days_per_week, weeks_per_year, holiday_sick_days,
                           incident_fte_time_pct):
    """Calculate the true cost per incident based on FTE time allocation"""
    if incident_volume == 0 or incident_ftes == 0:
        return 0, 0, 0, 0
    
    # Calculate total time required by the workload
    total_incident_time_minutes_per_year = incident_volume * avg_incident_triage_time
    total_incident_time_hours_per_year = total_incident_time_minutes_per_year / 60
    
    # Calculate total available hours from the FTE pool
    total_working_days = (weeks_per_year * days_per_week) - holiday_sick_days
    working_hours_per_fte_per_year = total_working_days * hours_per_day
    total_available_fte_hours = incident_ftes * working_hours_per_fte_per_year
    
    # 1. Calculate allocated hours
    total_allocated_fte_hours = total_available_fte_hours * (incident_fte_time_pct / 100.0)

    # 2. Calculate utilization within allocated time
    utilization_of_allocated_time = total_incident_time_hours_per_year / total_allocated_fte_hours if total_allocated_fte_hours > 0 else 0
    
    # 3. Calculate cost based on user-defined percentage
    total_fte_cost = incident_ftes * avg_salary_per_year
    total_incident_handling_cost = total_fte_cost * (incident_fte_time_pct / 100.0)
    
    cost_per_incident = total_incident_handling_cost / incident_volume if incident_volume > 0 else 0
    
    return cost_per_incident, total_incident_handling_cost, utilization_of_allocated_time, working_hours_per_fte_per_year

def calculate_asset_discovery_costs(asset_volume, manual_discovery_cycles_per_year, hours_per_discovery_cycle, 
                                   asset_management_ftes, avg_asset_mgmt_fte_salary,
                                   hours_per_day, days_per_week, weeks_per_year, holiday_sick_days,
                                   asset_mgmt_fte_time_pct):
    """Calculate the cost of manual asset discovery processes"""
    if asset_volume == 0 or asset_management_ftes == 0:
        return 0, 0, 0, 0
    
    # Calculate total time required by the workload
    total_discovery_hours_per_year = manual_discovery_cycles_per_year * hours_per_discovery_cycle
    
    # Calculate total available hours from the FTE pool
    total_working_days = (weeks_per_year * days_per_week) - holiday_sick_days
    working_hours_per_fte_per_year = total_working_days * hours_per_day
    total_available_fte_hours = asset_management_ftes * working_hours_per_fte_per_year
    
    # 1. Calculate allocated hours
    total_allocated_fte_hours = total_available_fte_hours * (asset_mgmt_fte_time_pct / 100.0)

    # 2. Calculate utilization within allocated time
    utilization_of_allocated_time = total_discovery_hours_per_year / total_allocated_fte_hours if total_allocated_fte_hours > 0 else 0
    
    # 3. Calculate cost based on user-defined percentage
    total_fte_cost = asset_management_ftes * avg_asset_mgmt_fte_salary
    total_discovery_cost = total_fte_cost * (asset_mgmt_fte_time_pct / 100.0)
    
    cost_per_discovery_cycle = total_discovery_cost / manual_discovery_cycles_per_year if manual_discovery_cycles_per_year > 0 else 0
    
    return cost_per_discovery_cycle, total_discovery_cost, utilization_of_allocated_time, working_hours_per_fte_per_year

def calculate_benefit_realization_factor(month, implementation_delay_months, ramp_up_months):
    """Calculate what percentage of benefits are realized in a given month"""
    if month <= implementation_delay_months:
        return 0.0  # No benefits during implementation
    elif month <= implementation_delay_months + ramp_up_months:
        # Linear ramp-up during ramp-up period
        months_since_golive = month - implementation_delay_months
        return months_since_golive / ramp_up_months
    else:
        return 1.0  # Full benefits realized

def calculate_platform_cost_factor(month, billing_start_month):
    """Calculate whether platform costs are incurred in a given month"""
    return 1.0 if month >= billing_start_month else 0.0

def calculate_scenario_results(benefits_multiplier, implementation_delay_multiplier, scenario_name, billing_start_month):
    """Calculate NPV, ROI, and payback for a given scenario"""
    # Get values from session state
    total_annual_benefits = st.session_state.get('total_annual_benefits', 100000)
    implementation_delay_months = st.session_state.get('implementation_delay', 6)
    benefits_ramp_up_months = st.session_state.get('benefits_ramp_up', 3)
    platform_cost = st.session_state.get('platform_cost', 0)
    services_cost = st.session_state.get('services_cost', 0)
    evaluation_years = st.session_state.get('evaluation_years', 3)
    discount_rate = st.session_state.get('discount_rate', 10) / 100
    
    # Adjust benefits and timeline
    scenario_benefits = total_annual_benefits * benefits_multiplier
    scenario_impl_delay = max(0, int(implementation_delay_months * implementation_delay_multiplier))
    scenario_ramp_up = benefits_ramp_up_months
    
    # Calculate cash flows
    scenario_cash_flows = []
    for year in range(1, evaluation_years + 1):
        year_start_month = (year - 1) * 12 + 1
        year_end_month = year * 12
        
        # Calculate monthly factors and average for the year
        monthly_benefit_factors = []
        monthly_cost_factors = []
        
        for month in range(year_start_month, year_end_month + 1):
            benefit_factor = calculate_benefit_realization_factor(month, scenario_impl_delay, scenario_ramp_up)
            cost_factor = calculate_platform_cost_factor(month, billing_start_month)
            monthly_benefit_factors.append(benefit_factor)
            monthly_cost_factors.append(cost_factor)
        
        avg_benefit_realization_factor = np.mean(monthly_benefit_factors)
        avg_cost_factor = np.mean(monthly_cost_factors)
        
        year_benefits = scenario_benefits * avg_benefit_realization_factor
        year_platform_cost = platform_cost * avg_cost_factor  # Only pay for months when billing is active
        year_services_cost = services_cost if year == 1 else 0
        year_net_cash_flow = year_benefits - year_platform_cost - year_services_cost
        
        scenario_cash_flows.append({
            'year': year,
            'benefits': year_benefits,
            'platform_cost': year_platform_cost,
            'services_cost': year_services_cost,
            'net_cash_flow': year_net_cash_flow,
            'benefit_realization_factor': avg_benefit_realization_factor,
            'cost_factor': avg_cost_factor
        })
    
    # Calculate metrics
    scenario_npv = sum([cf['net_cash_flow'] / ((1 + discount_rate) ** cf['year']) for cf in scenario_cash_flows])
    scenario_tco = sum([cf['platform_cost'] + cf['services_cost'] for cf in scenario_cash_flows])
    scenario_roi = scenario_npv / scenario_tco if scenario_tco != 0 else 0
    
    # Calculate payback
    scenario_payback = "N/A"
    cumulative_net_cash_flow = 0
    for cf in scenario_cash_flows:
        cumulative_net_cash_flow += cf['net_cash_flow']
        if cumulative_net_cash_flow >= 0:
            scenario_payback = f"{cf['year']} years"
            break
    
    return {
        'npv': scenario_npv,
        'roi': scenario_roi,
        'payback': scenario_payback,
        'impl_delay': scenario_impl_delay,
        'benefits_mult': benefits_multiplier,
        'cash_flows': scenario_cash_flows,
        'annual_benefits': scenario_benefits
    }

def calculate_payback_months(annual_benefits, annual_platform_cost, one_time_services_cost, 
                             implementation_delay_months, benefits_ramp_up_months, billing_start_month, max_months_eval=60):
    """Calculates the payback period in months."""
    
    cumulative_cash_flow = 0
    payback_month = "N/A"
    
    # Initial investment (services cost) incurred at the beginning
    cumulative_cash_flow -= one_time_services_cost

    for month in range(1, max_months_eval + 1):
        # Benefits start based on implementation timeline
        benefit_factor = calculate_benefit_realization_factor(month, implementation_delay_months, benefits_ramp_up_months)
        # Platform costs start based on billing timeline
        cost_factor = calculate_platform_cost_factor(month, billing_start_month)
        
        monthly_benefit = (annual_benefits / 12) * benefit_factor
        monthly_platform_cost = (annual_platform_cost / 12) * cost_factor
        
        monthly_net_cash_flow = monthly_benefit - monthly_platform_cost
        
        cumulative_cash_flow += monthly_net_cash_flow
        
        if cumulative_cash_flow >= 0:
            payback_month = f"{month} months"
            break
            
    return payback_month

def create_implementation_timeline_chart(implementation_delay_months, ramp_up_months, billing_start_month, evaluation_years, currency_symbol, total_annual_benefits):
    """Create a visual timeline showing benefit realization and cost timeline over time"""
    
    # Get platform cost from session state
    platform_cost = st.session_state.get('platform_cost', 0)
    
    total_months = evaluation_years * 12
    months = list(range(1, total_months + 1))
    benefit_realization_factors = []
    monthly_benefits = []
    monthly_costs = []
    
    for month in months:
        benefit_factor = calculate_benefit_realization_factor(month, implementation_delay_months, ramp_up_months)
        cost_factor = calculate_platform_cost_factor(month, billing_start_month)
        
        benefit_realization_factors.append(benefit_factor * 100)
        monthly_benefits.append(total_annual_benefits * benefit_factor / 12)
        monthly_costs.append(platform_cost * cost_factor / 12)
    
    fig = go.Figure()
    
    # Benefits line
    fig.add_trace(go.Scatter(
        x=months, y=benefit_realization_factors, mode='lines+markers', name='Benefit Realization %',
        line=dict(color='#2E86AB', width=3), marker=dict(size=4),
        hovertemplate='<b>Month %{x}</b><br>Benefit Realization: %{y:.1f}%<br><extra></extra>',
        yaxis='y'
    ))
    
    # Benefits area
    fig.add_trace(go.Scatter(
        x=months, y=[b/1000 for b in monthly_benefits], mode='lines', name=f'Monthly Benefits ({currency_symbol}K)',
        line=dict(color='#A23B72', width=2), fill='tonexty', fillcolor='rgba(162, 59, 114, 0.2)',
        hovertemplate='<b>Month %{x}</b><br>' + f'Monthly Benefit: {currency_symbol}' + '%{customdata:,.0f}<br><extra></extra>',
        customdata=monthly_benefits, yaxis='y2'
    ))
    
    # Platform costs line
    fig.add_trace(go.Scatter(
        x=months, y=[c/1000 for c in monthly_costs], mode='lines', name=f'Monthly Platform Costs ({currency_symbol}K)',
        line=dict(color='#FF6B6B', width=2, dash='dash'),
        hovertemplate='<b>Month %{x}</b><br>' + f'Monthly Platform Cost: {currency_symbol}' + '%{customdata:,.0f}<br><extra></extra>',
        customdata=monthly_costs, yaxis='y2'
    ))
    
    # Add milestone lines and phases
    if billing_start_month > 0:
        fig.add_vline(x=billing_start_month, line_dash="dot", line_color="blue", line_width=2,
                      annotation_text="Billing Starts", annotation_position="top")
    
    if implementation_delay_months > 0:
        fig.add_vline(x=implementation_delay_months, line_dash="dash", line_color="red", line_width=2,
                      annotation_text="Go-Live", annotation_position="top")
    
    if ramp_up_months > 0:
        fig.add_vline(x=implementation_delay_months + ramp_up_months, line_dash="dash", line_color="green", line_width=2,
                      annotation_text="Full Benefits", annotation_position="top")
    
    fig.update_layout(
        title={'text': 'Implementation Timeline: Benefits vs Platform Costs', 'x': 0.5, 'xanchor': 'center', 'font': {'size': 18}},
        xaxis_title="Months from Project Start",
        yaxis=dict(title="Benefit Realization (%)", side="left", range=[0, 105], color='#2E86AB'),
        yaxis2=dict(title=f"Monthly Value ({currency_symbol}K)", side="right", overlaying="y", color='#A23B72'),
        height=500, hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    return fig

# --- ENHANCED IMPLEMENTATION TIMELINE FUNCTIONS ---

def create_enhanced_implementation_timeline_chart(implementation_delay_months, ramp_up_months, billing_start_month, evaluation_years, currency_symbol, total_annual_benefits):
    """Create an enhanced visual timeline showing benefit realization progress"""
    
    total_months = evaluation_years * 12
    months = list(range(0, total_months + 1))  # Start from month 0
    
    # Initialize arrays
    benefit_realization_factors = []
    
    # Calculate values for each month
    for month in months:
        if month == 0:
            # Month 0: Initial setup
            benefit_factor = 0
        else:
            # Calculate factors for month
            benefit_factor = calculate_benefit_realization_factor(month, implementation_delay_months, ramp_up_months)
        
        # Store values
        benefit_realization_factors.append(benefit_factor * 100)
    
    # Create single chart
    fig = go.Figure()
    
    # Benefit Realization Percentage
    fig.add_trace(
        go.Scatter(
            x=months, 
            y=benefit_realization_factors, 
            mode='lines+markers', 
            name='Benefit Realization %',
            line=dict(color='#2E86AB', width=4),
            marker=dict(size=6, color='#2E86AB'),
            fill='tozeroy',
            fillcolor='rgba(46, 134, 171, 0.3)',
            hovertemplate='<b>Month %{x}</b><br>Benefit Realization: %{y:.1f}%<extra></extra>'
        )
    )
    
    # Add milestone lines and annotations
    milestones = []
    
    # Implementation phases
    if implementation_delay_months > 0:
        milestones.append({
            'x': implementation_delay_months,
            'label': '🚀 Go-Live',
            'color': '#ff6b35',
            'description': 'Benefits start to be realized'
        })
    
    if ramp_up_months > 0:
        full_benefits_month = implementation_delay_months + ramp_up_months
        milestones.append({
            'x': full_benefits_month,
            'label': '🎯 Full Benefits',
            'color': '#28a745',
            'description': '100% benefit realization achieved'
        })
    
    if billing_start_month > 0:
        milestones.append({
            'x': billing_start_month,
            'label': '💳 Billing Starts',
            'color': '#007bff',
            'description': 'Platform subscription begins'
        })
    
    # Add payback milestone using existing calculation
    expected_result = st.session_state.get('scenario_results', {}).get('Expected', {})
    payback_months_str = expected_result.get('payback_months', 'N/A')
    
    if payback_months_str != 'N/A' and 'months' in payback_months_str:
        try:
            payback_month = int(payback_months_str.split(' ')[0])
            if payback_month <= total_months:
                milestones.append({
                    'x': payback_month,
                    'label': '💰 Payback',
                    'color': '#6f42c1',
                    'description': 'Investment fully recovered'
                })
        except (ValueError, IndexError):
            pass  # Skip if parsing fails
    
    # Add milestone lines
    for milestone in milestones:
        x_pos = milestone['x']
        
        fig.add_vline(
            x=x_pos, 
            line_dash="dash", 
            line_color=milestone['color'], 
            line_width=2
        )
        
        # Add annotation
        fig.add_annotation(
            x=x_pos,
            y=105,
            text=milestone['label'],
            showarrow=True,
            arrowhead=2,
            arrowcolor=milestone['color'],
            arrowwidth=2,
            bgcolor="white",
            bordercolor=milestone['color'],
            borderwidth=1,
            font=dict(size=10, color=milestone['color'])
        )
    
    # Update layout
    fig.update_layout(
        title={
            'text': 'Implementation Timeline: Benefit Realization Progress',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18, 'color': '#2c3e50'}
        },
        height=400,
        hovermode='x unified',
        showlegend=False,
        margin=dict(t=80, b=80),
        plot_bgcolor='rgba(248, 249, 250, 0.8)',
        paper_bgcolor='white'
    )
    
    # Update axes
    fig.update_xaxes(
        title_text="Months from Project Start",
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray'
    )
    
    fig.update_yaxes(
        title_text="Benefit Realization (%)",
        range=[0, 110],
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray'
    )
    
    # Add phase annotations as shapes
    phases = [
        {'start': 0, 'end': implementation_delay_months, 'label': 'Implementation Phase', 'color': 'rgba(255, 107, 53, 0.1)'},
        {'start': implementation_delay_months, 'end': implementation_delay_months + ramp_up_months, 'label': 'Ramp-up Phase', 'color': 'rgba(255, 193, 7, 0.1)'},
        {'start': implementation_delay_months + ramp_up_months, 'end': total_months, 'label': 'Full Operation Phase', 'color': 'rgba(40, 167, 69, 0.1)'}
    ]
    
    for phase in phases:
        if phase['end'] > phase['start']:
            # Add phase background
            fig.add_vrect(
                x0=phase['start'], x1=phase['end'],
                fillcolor=phase['color'],
                layer="below",
                line_width=0
            )
            
            # Add phase label
            if phase['start'] < total_months:
                mid_point = (phase['start'] + min(phase['end'], total_months)) / 2
                fig.add_annotation(
                    x=mid_point,
                    y=-8,
                    text=phase['label'],
                    showarrow=False,
                    font=dict(size=9, color='#6c757d'),
                    bgcolor="rgba(255, 255, 255, 0.8)",
                    bordercolor="#dee2e6",
                    borderwidth=1
                )
    
    return fig

def create_timeline_summary_metrics(scenario_results, currency_symbol, implementation_delay_months, benefits_ramp_up_months):
    """Create summary metrics to accompany the timeline chart"""
    
    expected_result = scenario_results['Expected']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Time to Go-Live",
            f"{implementation_delay_months} months",
            help="Time from project start until benefits begin"
        )
    
    with col2:
        st.metric(
            "Time to Full Benefits",
            f"{implementation_delay_months + benefits_ramp_up_months} months",
            help="Time until 100% benefit realization"
        )
    
    with col3:
        payback_months = expected_result.get('payback_months', 'N/A')
        st.metric(
            "Payback Period",
            payback_months,
            help="Time to recover total investment"
        )
    
    with col4:
        if 'cash_flows' in expected_result:
            max_monthly_benefit = max([cf['benefits']/12 for cf in expected_result['cash_flows']])
            st.metric(
                "Peak Monthly Benefit",
                f"{currency_symbol}{max_monthly_benefit:,.0f}",
                help="Maximum monthly benefit during full operation"
            )
        else:
            st.metric("Peak Monthly Benefit", "N/A")

def show_enhanced_timeline_section():
    """Enhanced timeline section with better visualization and metrics"""
    
    st.subheader("📅 Implementation Timeline & Benefit Realization")
    
    # Add informational context
    st.info("""
    **Timeline Overview**: This visualization shows your implementation journey from project start through full benefit realization.
    The chart includes distinct phases, key milestones, and benefit realization progress over time.
    """)
    
    # Show summary metrics
    create_timeline_summary_metrics(
        scenario_results, 
        currency_symbol, 
        implementation_delay_months, 
        benefits_ramp_up_months
    )
    
    st.markdown("---")
    
    # Show the enhanced chart
    enhanced_timeline_fig = create_enhanced_implementation_timeline_chart(
        implementation_delay_months, 
        benefits_ramp_up_months, 
        billing_start_month,
        evaluation_years, 
        currency_symbol, 
        total_annual_benefits
    )
    
    st.plotly_chart(enhanced_timeline_fig, use_container_width=True)
    
    # Add explanation of phases
    with st.expander("📖 Understanding the Timeline Phases"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **🔧 Implementation Phase**
            - Platform setup and configuration
            - Team training and onboarding
            - Process integration
            - No benefits realized yet
            - Services costs incurred
            """)
        
        with col2:
            st.markdown("""
            **⬆️ Ramp-up Phase**
            - Gradual benefit realization
            - User adoption increases
            - Process optimization
            - Benefits grow linearly to 100%
            - Platform costs may begin
            """)
        
        with col3:
            st.markdown("""
            **🎯 Full Operation Phase**
            - 100% benefit realization
            - Steady-state operations
            - Continuous improvement
            - Maximum ROI period
            - Ongoing platform costs
            """)
    
    return enhanced_timeline_fig

# --- Sidebar Logo Upload and Export/Import Section ---
st.sidebar.header("🏢 Company Logo & Reports")

# Logo Upload Section
with st.sidebar.expander("🖼️ Upload Company Logo"):
    st.write("Upload your company logo for PDF executive reports.")
    
    uploaded_logo = st.file_uploader(
        "Choose logo file",
        type=['png', 'jpg', 'jpeg'],
        help="Upload PNG or JPG logo file (recommended: 300x150 pixels)"
    )
    
    if uploaded_logo is not None:
        # Display logo preview
        st.image(uploaded_logo, width=200, caption="Logo Preview")
        st.success("✅ Logo uploaded successfully!")
    else:
        st.info("No logo uploaded. PDF reports will be generated without logo.")

# PDF Executive Summary Section
with st.sidebar.expander("📄 Generate Executive Summary"):
    st.write("Create a comprehensive PDF executive summary report.")
    
    if st.button("Generate PDF Executive Summary", key="generate_pdf"):
        if not REPORT_DEPENDENCIES_AVAILABLE:
            st.error("❌ PDF generation requires additional dependencies. Please install reportlab and matplotlib.")
        else:
            with st.spinner("Generating PDF executive summary..."):
                try:
                    pdf_data, error = generate_executive_pdf_report(uploaded_logo)
                    
                    if error:
                        st.error(f"❌ Error generating PDF: {error}")
                    elif pdf_data:
                        # Generate filename with timestamp
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        solution_name = st.session_state.get('solution_name', 'AIOPs')
                        filename = f"BVA_Executive_Summary_{solution_name}_{timestamp}.pdf"
                        
                        st.download_button(
                            label="📥 Download Executive Summary PDF",
                            data=pdf_data,
                            file_name=filename,
                            mime="application/pdf"
                        )
                        st.success("✅ PDF executive summary generated successfully!")
                    else:
                        st.error("❌ Failed to generate PDF")
                        
                except Exception as e:
                    st.error(f"❌ Error generating PDF: {str(e)}")

st.sidebar.markdown("---")

st.sidebar.header("🔄 Configuration Export/Import")

# Export Section
with st.sidebar.expander("📤 Export Configuration"):
    st.write("Export your current configuration to save or share with others.")
    
    export_format = st.selectbox("Export Format", ["CSV", "JSON"], key="export_format")
    
    if st.button("Generate Export File"):
        current_values = get_all_input_values()
        
        if export_format == "CSV":
            export_data = export_to_csv(current_values)
            file_extension = "csv"
            mime_type = "text/csv"
        else:  # JSON
            export_data = export_to_json(current_values)
            file_extension = "json"
            mime_type = "application/json"
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"BVA_Config_{timestamp}.{file_extension}"
        
        st.download_button(
            label=f"Download {export_format} Configuration",
            data=export_data,
            file_name=filename,
            mime=mime_type
        )

# Import Section
with st.sidebar.expander("📥 Import Configuration"):
    st.write("Import a previously saved configuration.")
    
    uploaded_file = st.file_uploader(
        "Choose configuration file",
        type=['csv', 'json'],
        help="Upload a CSV or JSON configuration file"
    )
    
    if uploaded_file is not None:
        try:
            # Read file content
            file_content = uploaded_file.read().decode('utf-8')
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            if st.button("Import Configuration"):
                if file_extension == 'csv':
                    success, message = import_from_csv(file_content)
                elif file_extension == 'json':
                    success, message = import_from_json(file_content)
                else:
                    success, message = False, "Unsupported file format"
                
                if success:
                    st.success(message)
                    st.info("Please scroll down to see the imported values. You may need to refresh the page to see all changes.")
                else:
                    st.error(message)
        
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")

st.sidebar.markdown("---")

# --- Sidebar Inputs ---
st.sidebar.header("Customize Your Financial Impact Model Inputs")

# Solution Name Input
solution_name = st.sidebar.text_input("Customer Name", value="ACME", key="solution_name")

# --- Implementation Timeline ---
st.sidebar.subheader("📅 Implementation Timeline")
implementation_delay_months = st.sidebar.slider(
    "Implementation Delay (months)", 
    0, 24, 0, 
    help="Time from project start until benefits begin to be realized",
    key="implementation_delay"
)
benefits_ramp_up_months = st.sidebar.slider(
    "Benefits Ramp-up Period (months)", 
    0, 12, 0,
    help="Time to reach full benefits after go-live (gradual adoption)",
    key="benefits_ramp_up"
)
billing_start_month = st.sidebar.slider(
    "Billing Start Month", 
    1, 24, 1,
    help="Month when platform subscription billing begins (when customer starts paying monthly fees)",
    key="billing_start_month"
)
st.sidebar.caption("💡 Platform costs start from billing month. Benefits start when implementation completes (independent timelines)")

# --- Industry Benchmark Templates (removed compliance automation) ---
industry_templates = {
    "Custom": {},
    "Financial Services": {
        "alert_volume": 1_200_000,
        "major_incident_volume": 140,
        "avg_alert_triage_time": 25,
        "alert_reduction_pct": 40,
        "incident_volume": 400_000,
        "avg_incident_triage_time": 30,
        "incident_reduction_pct": 40,
        "mttr_improvement_pct": 40,
        # Asset management fields (no CMDB)
        "asset_volume": 15000,
        "manual_discovery_cycles_per_year": 4,
        "hours_per_discovery_cycle": 120,
        "asset_discovery_automation_pct": 70
    },
    "Retail": {
        "alert_volume": 600_000,
        "major_incident_volume": 80,
        "avg_alert_triage_time": 20,
        "alert_reduction_pct": 30,
        "incident_volume": 200_000,
        "avg_incident_triage_time": 25,
        "incident_reduction_pct": 30,
        "mttr_improvement_pct": 30,
        # Asset management fields (no CMDB)
        "asset_volume": 8000,
        "manual_discovery_cycles_per_year": 6,
        "hours_per_discovery_cycle": 80,
        "asset_discovery_automation_pct": 60
    },
    "MSP": {
        "alert_volume": 2_500_000,
        "major_incident_volume": 200,
        "avg_alert_triage_time": 35,
        "alert_reduction_pct": 50,
        "incident_volume": 800_000,
        "avg_incident_triage_time": 35,
        "incident_reduction_pct": 50,
        "mttr_improvement_pct": 50,
        # Asset management fields (no CMDB)
        "asset_volume": 25000,
        "manual_discovery_cycles_per_year": 12,
        "hours_per_discovery_cycle": 200,
        "asset_discovery_automation_pct": 80
    },
    "Healthcare": {
        "alert_volume": 800_000,
        "major_incident_volume": 100,
        "avg_alert_triage_time": 30,
        "alert_reduction_pct": 35,
        "incident_volume": 300_000,
        "avg_incident_triage_time": 30,
        "incident_reduction_pct": 35,
        "mttr_improvement_pct": 35,
        # Asset management fields (no CMDB)
        "asset_volume": 12000,
        "manual_discovery_cycles_per_year": 3,
        "hours_per_discovery_cycle": 100,
        "asset_discovery_automation_pct": 65
    },
    "Telecom": {
        "alert_volume": 1_800_000,
        "major_incident_volume": 160,
        "avg_alert_triage_time": 35,
        "alert_reduction_pct": 45,
        "incident_volume": 600_000,
        "avg_incident_triage_time": 35,
        "incident_reduction_pct": 40,
        "mttr_improvement_pct": 45,
        # Asset management fields (no CMDB)
        "asset_volume": 20000,
        "manual_discovery_cycles_per_year": 6,
        "hours_per_discovery_cycle": 150,
        "asset_discovery_automation_pct": 75
    }
}

selected_template = st.sidebar.selectbox("Select Industry Template", list(industry_templates.keys()), key="industry_template")
template = industry_templates[selected_template]
st.sidebar.caption("📌 Industry templates provide baseline values for estimation only. Adjust any field as needed.")

# --- Currency Selection ---
currency_symbol = st.sidebar.selectbox("Currency", ["$", "€", "£", "Kč"], key="currency")

# --- Working Hours Configuration ---
st.sidebar.subheader("⏰ Working Hours Configuration")
hours_per_day = st.sidebar.number_input(
    "Working Hours per Day", 
    value=8.0, 
    min_value=1.0, 
    max_value=24.0,
    step=0.5,
    key="hours_per_day",
    help="Standard working hours per day for your FTEs"
)
days_per_week = st.sidebar.number_input(
    "Working Days per Week", 
    value=5, 
    min_value=1, 
    max_value=7,
    key="days_per_week",
    help="Standard working days per week"
)
weeks_per_year = st.sidebar.number_input(
    "Working Weeks per Year", 
    value=52, 
    min_value=1, 
    max_value=52,
    key="weeks_per_year",
    help="Total weeks worked per year"
)
holiday_sick_days = st.sidebar.number_input(
    "Holiday + Sick Days per Year", 
    value=25, 
    min_value=0, 
    max_value=100,
    key="holiday_sick_days",
    help="Total days off per year (holidays, vacation, sick leave)"
)

# Calculate and display total working hours
total_working_days = (weeks_per_year * days_per_week) - holiday_sick_days
working_hours_per_fte_per_year = total_working_days * hours_per_day
st.sidebar.info(f"**Calculated: {working_hours_per_fte_per_year:,.0f} working hours per FTE per year**")

# --- ALERT INPUTS ---
st.sidebar.subheader("🚨 Alert Management")
alert_volume = st.sidebar.number_input(
    "Total Infrastructure Related Alerts Managed per Year", 
    value=template.get("alert_volume", 0),
    key="alert_volume"
)
alert_ftes = st.sidebar.number_input(
    "Total FTEs Managing Infrastructure Alerts", 
    value=0,
    key="alert_ftes"
)
alert_fte_time_pct = st.sidebar.slider(
    "% of FTE Time on Alerts", 0, 100, 100,
    help="The percentage of time the above FTEs dedicate specifically to managing these alerts.",
    key="alert_fte_time_pct"
)
avg_alert_triage_time = st.sidebar.number_input(
    "Average Alert Triage Time (minutes)", 
    value=template.get("avg_alert_triage_time", 0),
    key="avg_alert_triage_time"
)
avg_alert_fte_salary = st.sidebar.number_input(
    "Average Annual Salary per Alert Management FTE", 
    value=0,
    key="avg_alert_fte_salary"
)
alert_reduction_pct = st.sidebar.slider(
    "% Alert Reduction", 
    0, 100, 
    value=template.get("alert_reduction_pct", 0),
    key="alert_reduction_pct"
)
alert_triage_time_saved_pct = st.sidebar.slider(
    "% Alert Triage Time Reduction", 
    0, 100, 0,
    key="alert_triage_time_saved_pct"
)

# --- INCIDENT INPUTS ---
st.sidebar.subheader("🔧 Incident Management")
incident_volume = st.sidebar.number_input(
    "Total Infrastructure Related Incident Volumes Managed per Year", 
    value=template.get("incident_volume", 0),
    key="incident_volume"
)
incident_ftes = st.sidebar.number_input(
    "Total FTEs Managing Infrastructure Incidents", 
    value=0,
    key="incident_ftes"
)
incident_fte_time_pct = st.sidebar.slider(
    "% of FTE Time on Incidents", 0, 100, 100,
    help="The percentage of time the above FTEs dedicate specifically to managing these incidents.",
    key="incident_fte_time_pct"
)
avg_incident_triage_time = st.sidebar.number_input(
    "Average Incident Triage Time (minutes)", 
    value=template.get("avg_incident_triage_time", 0),
    key="avg_incident_triage_time"
)
avg_incident_fte_salary = st.sidebar.number_input(
    "Average Annual Salary per Incident Management FTE", 
    value=0,
    key="avg_incident_fte_salary"
)
incident_reduction_pct = st.sidebar.slider(
    "% Incident Reduction", 
    0, 100, 
    value=template.get("incident_reduction_pct", 0),
    key="incident_reduction_pct"
)
incident_triage_time_savings_pct = st.sidebar.slider(
    "% Incident Triage Time Reduction", 
    0, 100, 0,
    key="incident_triage_time_savings_pct"
)

# --- MAJOR INCIDENT INPUTS ---
st.sidebar.subheader("🚨 Major Incidents (Sev1)")
major_incident_volume = st.sidebar.number_input(
    "Total Infrastructure Related Major Incidents per Year (Sev1)", 
    value=template.get("major_incident_volume", 0),
    key="major_incident_volume"
)
avg_major_incident_cost = st.sidebar.number_input(
    "Average Major Incident Cost per Hour", 
    value=0,
    key="avg_major_incident_cost"
)
avg_mttr_hours = st.sidebar.number_input(
    "Average MTTR (hours)", 
    value=0.0,
    key="avg_mttr_hours"
)
mttr_improvement_pct = st.sidebar.slider(
    "MTTR Improvement Percentage", 
    0, 100, 
    value=template.get("mttr_improvement_pct", 0),
    key="mttr_improvement_pct"
)

# --- ASSET DISCOVERY INPUTS ---
st.sidebar.subheader("🏗️ Asset Discovery")

# Asset Discovery Automation
st.sidebar.markdown("**Asset Discovery Automation**")
asset_volume = st.sidebar.number_input(
    "Total IT Assets Under Management", 
    value=template.get("asset_volume", 0),
    key="asset_volume",
    help="Total number of IT assets (servers, network devices, applications, etc.)"
)
manual_discovery_cycles_per_year = st.sidebar.number_input(
    "Manual Discovery Cycles per Year", 
    value=template.get("manual_discovery_cycles_per_year", 0),
    key="manual_discovery_cycles_per_year",
    help="How often you manually discover/audit your IT assets"
)
hours_per_discovery_cycle = st.sidebar.number_input(
    "Hours per Manual Discovery Cycle", 
    value=template.get("hours_per_discovery_cycle", 0),
    key="hours_per_discovery_cycle",
    help="Total FTE hours spent on each manual discovery cycle"
)
asset_management_ftes = st.sidebar.number_input(
    "Total FTEs Managing IT Assets", 
    value=0,
    key="asset_management_ftes",
    help="FTEs involved in asset discovery"
)
asset_mgmt_fte_time_pct = st.sidebar.slider(
    "% of FTE Time on Asset Discovery", 0, 100, 100,
    help="The percentage of time the above FTEs dedicate to manual asset discovery.",
    key="asset_mgmt_fte_time_pct"
)
avg_asset_mgmt_fte_salary = st.sidebar.number_input(
    "Average Annual Salary per Asset Management FTE", 
    value=0,
    key="avg_asset_mgmt_fte_salary"
)
asset_discovery_automation_pct = st.sidebar.slider(
    "% Asset Discovery Process Automated", 
    0, 100, template.get("asset_discovery_automation_pct", 0),
    key="asset_discovery_automation_pct",
    help="Percentage of manual discovery process that can be automated"
)

# --- OTHER BENEFITS ---
st.sidebar.subheader("💰 Additional Benefits")
tool_savings = st.sidebar.number_input(
    "Tool Consolidation Savings", 
    value=0,
    key="tool_savings"
)
people_cost_per_year = st.sidebar.number_input(
    "People Efficiency Gains", 
    value=0,
    key="people_efficiency"
)
fte_avoidance = st.sidebar.number_input(
    "FTE Avoidance (annualized value in local currency)", 
    value=0,
    key="fte_avoidance"
)
sla_penalty_avoidance = st.sidebar.number_input(
    "SLA Penalty Avoidance (Service Providers)", 
    value=0,
    key="sla_penalty"
)
revenue_growth = st.sidebar.number_input(
    "Revenue Growth (Service Providers)", 
    value=0,
    key="revenue_growth"
)
capex_savings = st.sidebar.number_input(
    "Capital Expenditure Savings (Hardware)", 
    value=0,
    key="capex_savings"
)
opex_savings = st.sidebar.number_input(
    "Operational Expenditure Savings (e.g. Storage Costs)", 
    value=0,
    key="opex_savings"
)

# --- COSTS ---
st.sidebar.subheader("💳 Solution Costs")
platform_cost = st.sidebar.number_input(
    "Annual Subscription Cost (After discounts)", 
    value=0,
    key="platform_cost"
)
services_cost = st.sidebar.number_input(
    "Implementation & Services (One-Time)", 
    value=0,
    key="services_cost"
)

# --- FINANCIAL SETTINGS ---
st.sidebar.subheader("📊 Financial Analysis Settings")
evaluation_years = st.sidebar.slider(
    "Evaluation Period (Years)", 
    1, 5, 3,
    key="evaluation_years"
)
discount_rate = st.sidebar.slider(
    "NPV Discount Rate (%)", 
    0, 20, 3,
    key="discount_rate"
) / 100

# --- INPUT VALIDATION ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Input Validation")

warnings, errors = validate_inputs()

if errors:
    st.sidebar.error("❌ Please fix these errors:")
    for error in errors:
        st.sidebar.error(f"• {error}")

if warnings:
    st.sidebar.warning("⚠️ Please review these items:")
    for warning in warnings:
        st.sidebar.warning(f"• {warning}")

if not errors and not warnings:
    st.sidebar.success("✅ All inputs look good!")

# --- CORRECTED CALCULATIONS WITH CONFIGURABLE WORKING HOURS ---

# Calculate alert and incident costs
cost_per_alert, total_alert_handling_cost, alert_fte_percentage, alert_working_hours = calculate_alert_costs(
    alert_volume, alert_ftes, avg_alert_triage_time, avg_alert_fte_salary,
    hours_per_day, days_per_week, weeks_per_year, holiday_sick_days,
    alert_fte_time_pct
)

cost_per_incident, total_incident_handling_cost, incident_fte_percentage, incident_working_hours = calculate_incident_costs(
    incident_volume, incident_ftes, avg_incident_triage_time, avg_incident_fte_salary,
    hours_per_day, days_per_week, weeks_per_year, holiday_sick_days,
    incident_fte_time_pct
)

# Calculate asset discovery costs and savings
cost_per_discovery_cycle, total_discovery_cost, discovery_fte_percentage, discovery_working_hours = calculate_asset_discovery_costs(
    asset_volume, manual_discovery_cycles_per_year, hours_per_discovery_cycle, 
    asset_management_ftes, avg_asset_mgmt_fte_salary,
    hours_per_day, days_per_week, weeks_per_year, holiday_sick_days,
    asset_mgmt_fte_time_pct
)

# Asset discovery automation savings
asset_discovery_savings = total_discovery_cost * (asset_discovery_automation_pct / 100)

# Store calculated values in session state for use in other functions
st.session_state['cost_per_alert'] = cost_per_alert
st.session_state['cost_per_incident'] = cost_per_incident
st.session_state['total_alert_handling_cost'] = total_alert_handling_cost
st.session_state['total_incident_handling_cost'] = total_incident_handling_cost
st.session_state['alert_fte_percentage'] = alert_fte_percentage
st.session_state['incident_fte_percentage'] = incident_fte_percentage
st.session_state['working_hours_per_fte_per_year'] = working_hours_per_fte_per_year

# Store asset management calculated values in session state (no CMDB)
st.session_state['cost_per_discovery_cycle'] = cost_per_discovery_cycle
st.session_state['total_discovery_cost'] = total_discovery_cost
st.session_state['discovery_fte_percentage'] = discovery_fte_percentage
st.session_state['asset_discovery_savings'] = asset_discovery_savings

# Calculate baseline savings
avoided_alerts = alert_volume * (alert_reduction_pct / 100)
remaining_alerts = alert_volume - avoided_alerts
alert_reduction_savings = avoided_alerts * cost_per_alert
remaining_alert_handling_cost = remaining_alerts * cost_per_alert
alert_triage_savings = remaining_alert_handling_cost * (alert_triage_time_saved_pct / 100)

avoided_incidents = incident_volume * (incident_reduction_pct / 100)
remaining_incidents = incident_volume - avoided_incidents
incident_reduction_savings = avoided_incidents * cost_per_incident
remaining_incident_handling_cost = remaining_incidents * cost_per_incident
incident_triage_savings = remaining_incident_handling_cost * (incident_triage_time_savings_pct / 100)

mttr_hours_saved_per_incident = (mttr_improvement_pct / 100) * avg_mttr_hours
total_mttr_hours_saved = major_incident_volume * mttr_hours_saved_per_incident
major_incident_savings = total_mttr_hours_saved * avg_major_incident_cost

# Store calculated savings in session state
st.session_state['alert_reduction_savings'] = alert_reduction_savings
st.session_state['alert_triage_savings'] = alert_triage_savings
st.session_state['incident_reduction_savings'] = incident_reduction_savings
st.session_state['incident_triage_savings'] = incident_triage_savings
st.session_state['major_incident_savings'] = major_incident_savings

# Total Annual Benefits (UPDATED - NO CMDB SAVINGS)
total_annual_benefits = (
    alert_reduction_savings + alert_triage_savings + incident_reduction_savings +
    incident_triage_savings + major_incident_savings + tool_savings + people_cost_per_year +
    fte_avoidance + sla_penalty_avoidance + revenue_growth + capex_savings + opex_savings +
    # Asset management savings (no CMDB)
    asset_discovery_savings
)

st.session_state['total_annual_benefits'] = total_annual_benefits

# Calculate scenarios
scenarios = {
    "Conservative": {
        "benefits_multiplier": 0.7,  # 30% lower benefits
        "implementation_delay_multiplier": 1.3,  # 30% longer implementation
        "description": "Benefits 30% lower, implementation 30% longer",
        "color": "#ff6b6b",
        "icon": "🔴"
    },
    "Expected": {
        "benefits_multiplier": 1.0,  # Baseline
        "implementation_delay_multiplier": 1.0,  # Baseline
        "description": "Baseline assumptions as entered",
        "color": "#4ecdc4",
        "icon": "🟢"
    },
    "Optimistic": {
        "benefits_multiplier": 1.2,  # 20% higher benefits
        "implementation_delay_multiplier": 0.8,  # 20% faster implementation
        "description": "Benefits 20% higher, implementation 20% faster",
        "color": "#45b7d1",
        "icon": "🔵"
    }
}

scenario_results = {}
for scenario_name, params in scenarios.items():
    scenario_results[scenario_name] = calculate_scenario_results(
        params["benefits_multiplier"], 
        params["implementation_delay_multiplier"],
        scenario_name,
        billing_start_month
    )
    scenario_results[scenario_name].update({
        "color": params["color"],
        "description": params["description"],
        "icon": params["icon"]
    })

# Store scenario results in session state for PDF generation
st.session_state['scenario_results'] = scenario_results

# --- ENHANCED FUNCTIONALITY ADDITIONS ---

# 1. Calculate the total cost savings from alert and incident management
total_operational_savings_from_time_saved = (
    alert_reduction_savings + alert_triage_savings +
    incident_reduction_savings + incident_triage_savings +
    major_incident_savings
)

st.session_state['total_operational_savings_from_time_saved'] = total_operational_savings_from_time_saved

# 2. Determine the equivalent number of full-time employees (FTEs) from savings
effective_avg_fte_salary = 0
if avg_alert_fte_salary > 0 and avg_incident_fte_salary > 0:
    effective_avg_fte_salary = (avg_alert_fte_salary + avg_incident_fte_salary) / 2
elif avg_alert_fte_salary > 0:
    effective_avg_fte_salary = avg_alert_fte_salary
elif avg_incident_fte_salary > 0:
    effective_avg_fte_salary = avg_incident_fte_salary

equivalent_ftes_from_savings = 0
if effective_avg_fte_salary > 0:
    equivalent_ftes_from_savings = total_operational_savings_from_time_saved / effective_avg_fte_salary

st.session_state['equivalent_ftes_from_savings'] = equivalent_ftes_from_savings

# Update scenario results with monthly payback for each scenario
for scenario_name, params in scenarios.items():
    s_result = scenario_results[scenario_name]
    
    scenario_annual_benefits_for_payback = total_annual_benefits * params["benefits_multiplier"]
    scenario_impl_delay_for_payback = max(0, int(implementation_delay_months * params["implementation_delay_multiplier"]))
    
    s_result['payback_months'] = calculate_payback_months(
        annual_benefits=scenario_annual_benefits_for_payback,
        annual_platform_cost=platform_cost,
        one_time_services_cost=services_cost,
        implementation_delay_months=scenario_impl_delay_for_payback,
        benefits_ramp_up_months=benefits_ramp_up_months,
        billing_start_month=billing_start_month,
        max_months_eval=evaluation_years * 12
    )

# --- Main App Layout ---
st.title(f"Autonomous IT Operations Business Value Assessment for {solution_name} Implementation")
st.markdown("This comprehensive tool provides detailed financial analysis with enhanced ROI calculations, calculation reasoning, and data quality validation.")

# Display calculation health check in main area
calc_issues = check_calculation_health()
if calc_issues:
    st.warning("⚠️ **Calculation Health Check:**")
    for issue in calc_issues:
        st.warning(f"• {issue}")
    st.info("💡 Consider adjusting your inputs if these don't seem realistic.")

st.header("📊 Executive Financial Summary")

# --- Enhanced Key Metrics Cards ---
col1, col2, col3 = st.columns(3)

with col1:
    expected_npv = scenario_results['Expected']['npv']
    st.metric(label=f"Expected NPV ({evaluation_years} years)",
              value=f"{currency_symbol}{expected_npv:,.0f}")
    
with col2:
    expected_roi = scenario_results['Expected']['roi'] * 100
    st.metric(label=f"Expected ROI ({evaluation_years} years)",
              value=f"{expected_roi:.1f}%")

with col3:
    expected_payback = scenario_results['Expected']['payback']
    expected_payback_months = scenario_results['Expected']['payback_months']
    st.metric(label="Payback Period",
              value=f"{expected_payback_months}")

# Asset Management Value Summary (no CMDB)
if asset_discovery_savings > 0:
    st.markdown("---")
    st.subheader("🏗️ Asset Discovery Value")
    
    st.metric("Asset Discovery Automation", f"{currency_symbol}{asset_discovery_savings:,.0f}")

st.markdown("---")

# --- NEW: ENHANCED VALIDATION SECTION WITH CALCULATION REASONING ---
show_enhanced_validation_section()

st.markdown("---")

# --- ENHANCED ROI & CALCULATION BREAKDOWN ---
st.header("🧮 Enhanced ROI & Calculation Analysis")
st.info("Understanding exactly how your return on investment is calculated and what drives the numbers.")

# Create tabs for different calculation views
calc_tabs = st.tabs(["ROI Formula", "Step-by-Step Calculation", "Benefit Breakdown", "Cost Analysis", "Interactive Calculator", "Risk Analysis"])

with calc_tabs[0]:
    st.subheader("📐 ROI Calculation Formula")
    
    # Display the ROI formula with actual numbers
    total_benefits_3yr = sum([cf['benefits'] for cf in scenario_results['Expected']['cash_flows']])
    total_costs_3yr = sum([cf['platform_cost'] + cf['services_cost'] for cf in scenario_results['Expected']['cash_flows']])
    simple_roi = ((total_benefits_3yr - total_costs_3yr) / total_costs_3yr) * 100 if total_costs_3yr > 0 else 0
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        ### Basic ROI Formula:
        ```
        ROI = (Total Benefits - Total Costs) / Total Costs × 100%
        ```
        
        **Your Numbers:**
        - **Total Benefits ({evaluation_years} years):** {currency_symbol}{total_benefits_3yr:,.0f}
        - **Total Costs ({evaluation_years} years):** {currency_symbol}{total_costs_3yr:,.0f}
        - **Net Benefit:** {currency_symbol}{total_benefits_3yr - total_costs_3yr:,.0f}
        - **Simple ROI:** {simple_roi:.1f}%
        """)
    
    with col2:
        st.markdown(f"""
        ### NPV-Based ROI Formula (What we use):
        ```
        ROI = NPV / Total Investment × 100%
        ```
        
        **Your NPV-Based ROI:**
        - **Net Present Value:** {currency_symbol}{scenario_results['Expected']['npv']:,.0f}
        - **Total Investment:** {currency_symbol}{total_costs_3yr:,.0f}
        - **NPV-Based ROI:** {scenario_results['Expected']['roi']*100:.1f}%
        
        **Why NPV-Based ROI is Better:**
        - Accounts for time value of money (discount rate: {discount_rate*100:.1f}%)
        - Reflects realistic cash flow timing
        - Considers implementation delays and ramp-up periods
        """)
    
    # Visual ROI breakdown
    roi_data = {
        'Component': ['Total Benefits', 'Total Costs', 'Net Benefit'],
        'Amount': [total_benefits_3yr, -total_costs_3yr, total_benefits_3yr - total_costs_3yr],
        'Color': ['green', 'red', 'blue']
    }
    
    fig_roi = px.bar(roi_data, x='Component', y='Amount', color='Color',
                     title=f'ROI Components ({evaluation_years}-Year View)',
                     labels={'Amount': f'Amount ({currency_symbol})'})
    fig_roi.update_layout(showlegend=False)
    st.plotly_chart(fig_roi, use_container_width=True)

with calc_tabs[1]:
    st.subheader("🔢 Step-by-Step NPV Calculation")
    
    st.markdown("### How We Calculate Your NPV and ROI:")
    
    # Create detailed calculation table
    calc_data = []
    npv_running_total = 0
    
    for i, cf in enumerate(scenario_results['Expected']['cash_flows']):
        present_value = cf['net_cash_flow'] / ((1 + discount_rate) ** cf['year'])
        npv_running_total += present_value
        
        calc_data.append({
            'Year': cf['year'],
            'Benefits': f"{currency_symbol}{cf['benefits']:,.0f}",
            'Platform Cost': f"{currency_symbol}{cf['platform_cost']:,.0f}",
            'Services Cost': f"{currency_symbol}{cf['services_cost']:,.0f}",
            'Net Cash Flow': f"{currency_symbol}{cf['net_cash_flow']:,.0f}",
            'Discount Factor': f"1/(1.{int(discount_rate*100):02d})^{cf['year']} = {1/((1+discount_rate)**cf['year']):.3f}",
            'Present Value': f"{currency_symbol}{present_value:,.0f}",
            'Cumulative NPV': f"{currency_symbol}{npv_running_total:,.0f}"
        })
    
    calc_df = pd.DataFrame(calc_data)
    st.dataframe(calc_df, hide_index=True, use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Final NPV", f"{currency_symbol}{scenario_results['Expected']['npv']:,.0f}")
        st.metric("Total Investment", f"{currency_symbol}{total_costs_3yr:,.0f}")
    with col2:
        st.metric("NPV-Based ROI", f"{scenario_results['Expected']['roi']*100:.1f}%")
        st.metric("Payback Period", scenario_results['Expected']['payback_months'])

with calc_tabs[2]:
    st.subheader("💰 Detailed Benefit Breakdown")
    
    # Create comprehensive benefit calculation breakdown
    st.markdown("### How Each Benefit is Calculated:")
    
    # Alert Management Benefits
    st.markdown("#### 🚨 Alert Management Benefits")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        **Alert Reduction Savings:**
        - Alerts avoided: {avoided_alerts:,.0f} ({alert_reduction_pct}% of {alert_volume:,.0f})
        - Cost per alert: {currency_symbol}{cost_per_alert:.2f}
        - **Total savings: {currency_symbol}{alert_reduction_savings:,.0f}**
        """)
    
    with col2:
        st.markdown(f"""
        **Alert Triage Time Savings:**
        - Remaining alerts: {remaining_alerts:,.0f}
        - Time saved per alert: {alert_triage_time_saved_pct}%
        - **Total savings: {currency_symbol}{alert_triage_savings:,.0f}**
        """)

    # Incident Management Benefits
    st.markdown("#### 🔧 Incident Management Benefits")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        **Incident Reduction Savings:**
        - Incidents avoided: {avoided_incidents:,.0f} ({incident_reduction_pct}% of {incident_volume:,.0f})
        - Cost per incident: {currency_symbol}{cost_per_incident:.2f}
        - **Total savings: {currency_symbol}{incident_reduction_savings:,.0f}**
        """)
    
    with col2:
        st.markdown(f"""
        **Incident Triage Time Savings:**
        - Remaining incidents: {remaining_incidents:,.0f}
        - Time saved per incident: {incident_triage_time_savings_pct}%
        - **Total savings: {currency_symbol}{incident_triage_savings:,.0f}**
        """)

    # Major Incident MTTR Benefits
    if major_incident_savings > 0:
        st.markdown("#### 🚨 Major Incident MTTR Benefits")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            **MTTR Improvement Calculation:**
            - Major incidents per year: {major_incident_volume:,.0f}
            - Current avg MTTR: {avg_mttr_hours:.1f} hours
            - MTTR improvement: {mttr_improvement_pct}%
            - Hours saved per incident: {mttr_hours_saved_per_incident:.1f}
            """)
        
        with col2:
            st.markdown(f"""
            **MTTR Financial Impact:**
            - Total hours saved annually: {total_mttr_hours_saved:.1f}
            - Cost per major incident hour: {currency_symbol}{avg_major_incident_cost:,.0f}
            - **Total MTTR savings: {currency_symbol}{major_incident_savings:,.0f}**
            """)

    # Asset Management Benefits (no CMDB)
    if asset_discovery_savings > 0:
        st.markdown("#### 🏗️ Asset Discovery Benefits")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            **Asset Discovery Automation:**
            - Total assets under management: {asset_volume:,.0f}
            - Manual discovery cycles per year: {manual_discovery_cycles_per_year}
            - Hours per discovery cycle: {hours_per_discovery_cycle}
            - Annual discovery cost: {currency_symbol}{total_discovery_cost:,.0f}
            """)
        
        with col2:
            st.markdown(f"""
            **Discovery Automation Value:**
            - Process automation percentage: {asset_discovery_automation_pct}%
            - FTE time freed up: {discovery_fte_percentage*asset_discovery_automation_pct/100*100:.1f}% of {asset_management_ftes} FTEs
            - **Total discovery savings: {currency_symbol}{asset_discovery_savings:,.0f}**
            """)

    # Additional Benefits Summary
    other_benefits_total = tool_savings + people_cost_per_year + fte_avoidance + sla_penalty_avoidance + revenue_growth + capex_savings + opex_savings
    if other_benefits_total > 0:
        st.markdown("#### 💰 Additional Benefits")
        
        additional_benefits_data = []
        if tool_savings > 0:
            additional_benefits_data.append(("Tool Consolidation Savings", tool_savings, "Reduction in tool licensing and maintenance costs"))
        if people_cost_per_year > 0:
            additional_benefits_data.append(("People Efficiency Gains", people_cost_per_year, "Productivity improvements and efficiency gains"))
        if fte_avoidance > 0:
            additional_benefits_data.append(("FTE Avoidance", fte_avoidance, "Cost avoidance from not hiring additional staff"))
        if sla_penalty_avoidance > 0:
            additional_benefits_data.append(("SLA Penalty Avoidance", sla_penalty_avoidance, "Avoided penalties from improved service levels"))
        if revenue_growth > 0:
            additional_benefits_data.append(("Revenue Growth", revenue_growth, "Additional revenue from improved service delivery"))
        if capex_savings > 0:
            additional_benefits_data.append(("CAPEX Savings", capex_savings, "Reduced capital expenditure requirements"))
        if opex_savings > 0:
            additional_benefits_data.append(("OPEX Savings", opex_savings, "Operational expenditure reductions"))
        
        for benefit_name, benefit_value, benefit_description in additional_benefits_data:
            st.markdown(f"""
            **{benefit_name}:** {currency_symbol}{benefit_value:,.0f}  
            *{benefit_description}*
            """)

    # Total Benefits Summary
    st.markdown("#### 📊 Total Benefits Summary")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        operational_total = alert_reduction_savings + alert_triage_savings + incident_reduction_savings + incident_triage_savings + major_incident_savings
        st.metric("Operational Benefits", f"{currency_symbol}{operational_total:,.0f}")
    
    with col2:
        asset_mgmt_total = asset_discovery_savings
        st.metric("Asset Discovery Benefits", f"{currency_symbol}{asset_mgmt_total:,.0f}")
    
    with col3:
        st.metric("Additional Benefits", f"{currency_symbol}{other_benefits_total:,.0f}")
    
    st.markdown(f"**🎯 Total Annual Benefits: {currency_symbol}{total_annual_benefits:,.0f}**")
    
    # Before/After Comparison Table
    st.markdown("#### 📊 Before vs After Operational Comparison")
    comparison_df = create_before_after_comparison()
    st.dataframe(comparison_df, hide_index=True, use_container_width=True)

with calc_tabs[3]:
    st.subheader("💳 Cost Analysis")
    
    # Detailed cost breakdown
    st.markdown("### Total Cost of Ownership (TCO) Breakdown")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        **Annual Platform Costs:**
        - Year 1: {currency_symbol}{scenario_results['Expected']['cash_flows'][0]['platform_cost']:,.0f}
        - Year 2: {currency_symbol}{scenario_results['Expected']['cash_flows'][1]['platform_cost']:,.0f}
        - Year 3: {currency_symbol}{scenario_results['Expected']['cash_flows'][2]['platform_cost']:,.0f}
        - **Total Platform Costs: {currency_symbol}{sum([cf['platform_cost'] for cf in scenario_results['Expected']['cash_flows']]):,.0f}**
        """)
    
    with col2:
        st.markdown(f"""
        **One-Time Costs:**
        - Implementation & Services: {currency_symbol}{services_cost:,.0f}
        - **Total One-Time Costs: {currency_symbol}{services_cost:,.0f}**
        
        **Total Investment:**
        - Platform (3 years): {currency_symbol}{sum([cf['platform_cost'] for cf in scenario_results['Expected']['cash_flows']]):,.0f}
        - Services (one-time): {currency_symbol}{services_cost:,.0f}
        - **Total TCO: {currency_symbol}{total_costs_3yr:,.0f}**
        """)

with calc_tabs[4]:
    st.subheader("🔄 Interactive ROI Calculator")
    st.info("Adjust the sliders below to see how changes affect your ROI in real-time.")
    
    # Sync interactive slider values with main configuration values
    # This ensures imported configurations work properly
    if 'sync_interactive_sliders' not in st.session_state:
        st.session_state['sync_interactive_sliders'] = True
    
    # Get current values from main configuration (respects imported values)
    current_alert_reduction = st.session_state.get('alert_reduction_pct', 0)
    current_incident_reduction = st.session_state.get('incident_reduction_pct', 0)
    current_mttr_improvement = st.session_state.get('mttr_improvement_pct', 0)
    current_implementation_delay = st.session_state.get('implementation_delay', 6)
    current_discount_rate = st.session_state.get('discount_rate', 10)
    current_asset_discovery_automation = st.session_state.get('asset_discovery_automation_pct', 0)
    
    # Interactive sliders for key variables
    col1, col2, col3 = st.columns(3)
    
    with col1:
        interactive_alert_reduction = st.slider(
            "Alert Reduction %", 0, 100, current_alert_reduction,
            key="interactive_alert_reduction"
        )
        interactive_incident_reduction = st.slider(
            "Incident Reduction %", 0, 100, current_incident_reduction,
            key="interactive_incident_reduction"
        )
    
    with col2:
        interactive_mttr_improvement = st.slider(
            "MTTR Improvement %", 0, 100, current_mttr_improvement,
            key="interactive_mttr_improvement"
        )
        interactive_platform_cost_mult = st.slider(
            "Platform Cost Multiplier", 0.5, 2.0, 1.0, 0.1,
            key="interactive_platform_cost"
        )
    
    with col3:
        interactive_implementation_delay = st.slider(
            "Implementation Delay (months)", 1, 24, current_implementation_delay,
            key="interactive_implementation_delay"
        )
        interactive_asset_automation = st.slider(
            "Asset Discovery Automation %", 0, 100, current_asset_discovery_automation,
            key="interactive_asset_automation"
        )
    
    # Add a reset button to sync sliders with main configuration
    if st.button("🔄 Reset Sliders to Current Configuration", key="reset_interactive_sliders"):
        # Clear the interactive slider keys from session state so they reinitialize with current values
        keys_to_clear = [
            'interactive_alert_reduction', 'interactive_incident_reduction', 
            'interactive_mttr_improvement', 'interactive_platform_cost',
            'interactive_implementation_delay', 'interactive_asset_automation'
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    # Calculate interactive results (CORRECTED to match original calculation method)
    # Alert savings - both reduction and triage efficiency
    interactive_avoided_alerts = alert_volume * (interactive_alert_reduction / 100)
    interactive_remaining_alerts = alert_volume - interactive_avoided_alerts
    interactive_alert_reduction_savings = interactive_avoided_alerts * cost_per_alert
    interactive_remaining_alert_handling_cost = interactive_remaining_alerts * cost_per_alert
    interactive_alert_triage_savings = interactive_remaining_alert_handling_cost * (alert_triage_time_saved_pct / 100)
    
    # Incident savings - both reduction and triage efficiency  
    interactive_avoided_incidents = incident_volume * (interactive_incident_reduction / 100)
    interactive_remaining_incidents = incident_volume - interactive_avoided_incidents
    interactive_incident_reduction_savings = interactive_avoided_incidents * cost_per_incident
    interactive_remaining_incident_handling_cost = interactive_remaining_incidents * cost_per_incident
    interactive_incident_triage_savings = interactive_remaining_incident_handling_cost * (incident_triage_time_savings_pct / 100)
    
    # MTTR savings
    interactive_mttr_savings = major_incident_volume * (interactive_mttr_improvement / 100) * avg_mttr_hours * avg_major_incident_cost
    
    # Asset management savings with interactive automation percentage
    interactive_asset_discovery_savings = total_discovery_cost * (interactive_asset_automation / 100)
    
    # Total interactive benefits (now matches original calculation method, no CMDB)
    interactive_total_benefits = (interactive_alert_reduction_savings + interactive_alert_triage_savings + 
                                interactive_incident_reduction_savings + interactive_incident_triage_savings + 
                                interactive_mttr_savings + tool_savings + people_cost_per_year + 
                                fte_avoidance + sla_penalty_avoidance + revenue_growth + 
                                capex_savings + opex_savings + interactive_asset_discovery_savings)
    
    # Calculate interactive NPV using the SAME method as original (accounts for billing timing)
    interactive_cash_flows = []
    for year in range(1, evaluation_years + 1):
        year_start_month = (year - 1) * 12 + 1
        year_end_month = year * 12
        
        # Calculate monthly factors and average for the year (same as original)
        monthly_benefit_factors = []
        monthly_cost_factors = []
        
        for month in range(year_start_month, year_end_month + 1):
            benefit_factor = calculate_benefit_realization_factor(month, interactive_implementation_delay, benefits_ramp_up_months)
            cost_factor = calculate_platform_cost_factor(month, billing_start_month)
            monthly_benefit_factors.append(benefit_factor)
            monthly_cost_factors.append(cost_factor)
        
        avg_benefit_realization_factor = np.mean(monthly_benefit_factors)
        avg_cost_factor = np.mean(monthly_cost_factors)
        
        year_benefits = interactive_total_benefits * avg_benefit_realization_factor
        year_platform_cost = platform_cost * interactive_platform_cost_mult * avg_cost_factor
        year_services_cost = services_cost if year == 1 else 0
        year_net_cash_flow = year_benefits - year_platform_cost - year_services_cost
        
        interactive_cash_flows.append({
            'year': year,
            'benefits': year_benefits,
            'platform_cost': year_platform_cost,
            'services_cost': year_services_cost,
            'net_cash_flow': year_net_cash_flow
        })
    
    # Calculate NPV and total costs using the same method as original
    interactive_npv = sum([cf['net_cash_flow'] / ((1 + discount_rate) ** cf['year']) for cf in interactive_cash_flows])
    interactive_total_costs = sum([cf['platform_cost'] + cf['services_cost'] for cf in interactive_cash_flows])
    interactive_roi = (interactive_npv / interactive_total_costs * 100) if interactive_total_costs > 0 else 0
    
    # Display interactive results
    st.markdown("### Interactive Results vs Original")
    
    # Show sync status
    if (interactive_alert_reduction == current_alert_reduction and 
        interactive_incident_reduction == current_incident_reduction and
        interactive_mttr_improvement == current_mttr_improvement and
        interactive_platform_cost_mult == 1.0 and
        interactive_implementation_delay == current_implementation_delay and
        interactive_asset_automation == current_asset_discovery_automation):
        st.success("✅ Sliders match current configuration - results should show 0% change")
    else:
        st.info("ℹ️ Sliders modified from current configuration")
    
    result_col1, result_col2, result_col3, result_col4 = st.columns(4)
    
    # Use the same calculation method for original values
    original_total_costs = sum([cf['platform_cost'] + cf['services_cost'] for cf in scenario_results['Expected']['cash_flows']])
    
    original_values = {
        'benefits': total_annual_benefits,
        'costs': original_total_costs,
        'npv': scenario_results['Expected']['npv'],
        'roi': scenario_results['Expected']['roi'] * 100
    }
    
    with result_col1:
        benefit_change = ((interactive_total_benefits - original_values['benefits']) / original_values['benefits'] * 100) if original_values['benefits'] != 0 else 0
        st.metric(
            "Annual Benefits",
            f"{currency_symbol}{interactive_total_benefits:,.0f}",
            f"{benefit_change:+.1f}%"
        )
    
    with result_col2:
        cost_change = ((interactive_total_costs - original_values['costs']) / original_values['costs'] * 100) if original_values['costs'] != 0 else 0
        st.metric(
            "Total Costs",
            f"{currency_symbol}{interactive_total_costs:,.0f}",
            f"{cost_change:+.1f}%"
        )
    
    with result_col3:
        npv_change = ((interactive_npv - original_values['npv']) / original_values['npv'] * 100) if original_values['npv'] != 0 else 0
        st.metric(
            "NPV",
            f"{currency_symbol}{interactive_npv:,.0f}",
            f"{npv_change:+.1f}%"
        )
    
    with result_col4:
        roi_change = interactive_roi - original_values['roi']
        st.metric(
            "ROI",
            f"{interactive_roi:.1f}%",
            f"{roi_change:+.1f}%"
        )

with calc_tabs[5]:
    st.subheader("⚠️ Risk Analysis & Monte Carlo Simulation")
    
    # Monte Carlo Analysis
    st.markdown("### Monte Carlo Simulation Results")
    st.info("This simulation runs 1,000 scenarios with random variations in key inputs to show the range of possible outcomes.")
    
    if st.button("Run Monte Carlo Simulation", key="run_monte_carlo"):
        with st.spinner("Running 1,000 simulations..."):
            roi_results, npv_results = run_monte_carlo_simulation()
        
        # Display results
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Median ROI", f"{np.median(roi_results):.1f}%")
            st.metric("ROI Range (95%)", f"{np.percentile(roi_results, 2.5):.1f}% to {np.percentile(roi_results, 97.5):.1f}%")
        
        with col2:
            st.metric("Median NPV", f"{currency_symbol}{np.median(npv_results):,.0f}")
            st.metric("NPV Range (95%)", f"{currency_symbol}{np.percentile(npv_results, 2.5):,.0f} to {currency_symbol}{np.percentile(npv_results, 97.5):,.0f}")
        
        with col3:
            positive_roi_pct = (np.array(roi_results) > 0).mean() * 100
            positive_npv_pct = (np.array(npv_results) > 0).mean() * 100
            st.metric("Positive ROI Probability", f"{positive_roi_pct:.1f}%")
            st.metric("Positive NPV Probability", f"{positive_npv_pct:.1f}%")
        
        # ROI Distribution Chart
        fig_roi_dist = px.histogram(
            x=roi_results, 
            nbins=50,
            title='ROI Distribution from Monte Carlo Simulation',
            labels={'x': 'ROI (%)', 'y': 'Frequency'},
            opacity=0.7
        )
        fig_roi_dist.add_vline(x=np.median(roi_results), line_dash="dash", line_color="red", 
                               annotation_text=f"Median: {np.median(roi_results):.1f}%")
        st.plotly_chart(fig_roi_dist, use_container_width=True)

st.markdown("---")

# --- Scenario Analysis ---
st.header("📈 Scenario Analysis")
st.info("Explore the potential financial outcomes under different assumptions.")

tabs = st.tabs(list(scenarios.keys()))

for i, (scenario_name, params) in enumerate(scenarios.items()):
    with tabs[i]:
        result = scenario_results[scenario_name]
        st.subheader(f"{params['icon']} {scenario_name} Scenario")
        st.markdown(f"*{params['description']}*")

        st.markdown("---")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Net Present Value (NPV)", f"{currency_symbol}{result['npv']:,.0f}")
        with col2:
            st.metric("Return on Investment (ROI)", f"{result['roi']*100:.1f}%")
        with col3:
            st.metric("Payback Period (Years)", result['payback'])
        with col4:
            st.metric("Payback Period (Months)", result['payback_months'])

        # Display cash flows in a table
        st.markdown("#### Detailed Cash Flows")
        cash_flow_df = pd.DataFrame(result['cash_flows'])
        cash_flow_df['net_cash_flow_cumulative'] = cash_flow_df['net_cash_flow'].cumsum()

        # Format for display
        cash_flow_display_df = cash_flow_df.copy()
        for col in ['benefits', 'platform_cost', 'services_cost', 'net_cash_flow', 'net_cash_flow_cumulative']:
            cash_flow_display_df[col] = cash_flow_display_df[col].apply(lambda x: f"{currency_symbol}{x:,.0f}")
        
        cash_flow_display_df['benefit_realization_factor'] = cash_flow_display_df['benefit_realization_factor'].apply(lambda x: f"{x*100:.1f}%")

        st.dataframe(cash_flow_display_df[[
            'year', 'benefits', 'platform_cost', 'services_cost', 
            'net_cash_flow', 'net_cash_flow_cumulative', 'benefit_realization_factor'
        ]].rename(columns={
            'year': 'Year',
            'benefits': 'Benefits',
            'platform_cost': 'Platform Cost',
            'services_cost': 'Services Cost',
            'net_cash_flow': 'Net Cash Flow',
            'net_cash_flow_cumulative': 'Cumulative Net Cash Flow',
            'benefit_realization_factor': 'Benefit Realization Factor'
        }), hide_index=True)

st.markdown("---")

# --- Enhanced Financial Analysis ---
st.subheader("📊 Enhanced Financial Visualizations")

# Create tabs for different visualizations
viz_tabs = st.tabs(["Benefits Breakdown", "Cost vs Benefits", "ROI Analysis", "Time-based Analysis"])

with viz_tabs[0]:
    benefits_chart = create_benefit_breakdown_chart(currency_symbol)
    if benefits_chart:
        st.plotly_chart(benefits_chart, use_container_width=True)
    else:
        st.info("No benefits to display. Please enter some benefit values in the sidebar.")
    
    # Add summary statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        operational_savings = alert_reduction_savings + alert_triage_savings + incident_reduction_savings + incident_triage_savings + major_incident_savings
        st.metric("Operational Savings", f"{currency_symbol}{operational_savings:,.0f}")
    with col2:
        asset_mgmt_savings = asset_discovery_savings
        st.metric("Asset Discovery Savings", f"{currency_symbol}{asset_mgmt_savings:,.0f}")
    with col3:
        cost_reduction = tool_savings + capex_savings + opex_savings
        st.metric("Cost Reduction", f"{currency_symbol}{cost_reduction:,.0f}")

with viz_tabs[1]:
    st.plotly_chart(create_cost_vs_benefit_waterfall(currency_symbol), use_container_width=True)

with viz_tabs[2]:
    st.plotly_chart(create_roi_comparison_chart(scenario_results, currency_symbol), use_container_width=True)

with viz_tabs[3]:
    # Enhanced timeline analysis
    months_range = list(range(0, evaluation_years * 12 + 1))
    cumulative_benefits = []
    cumulative_costs = []
    cumulative_net = []
    
    cum_benefit = 0
    cum_cost = services_cost  # Initial services cost
    
    for month in months_range:
        if month > 0:
            benefit_factor = calculate_benefit_realization_factor(month, implementation_delay_months, benefits_ramp_up_months)
            cost_factor = calculate_platform_cost_factor(month, billing_start_month)
            
            monthly_benefit = (total_annual_benefits / 12) * benefit_factor
            monthly_cost = (platform_cost / 12) * cost_factor
            
            cum_benefit += monthly_benefit
            cum_cost += monthly_cost
        
        cumulative_benefits.append(cum_benefit)
        cumulative_costs.append(cum_cost)
        cumulative_net.append(cum_benefit - cum_cost)
    
    fig_cumulative = go.Figure()
    
    fig_cumulative.add_trace(go.Scatter(
        x=months_range, y=cumulative_benefits, mode='lines', name='Cumulative Benefits',
        line=dict(color='green', width=2), fill='tonexty'
    ))
    
    fig_cumulative.add_trace(go.Scatter(
        x=months_range, y=cumulative_costs, mode='lines', name='Cumulative Costs',
        line=dict(color='red', width=2)
    ))
    
    fig_cumulative.add_trace(go.Scatter(
        x=months_range, y=cumulative_net, mode='lines', name='Net Position',
        line=dict(color='blue', width=3, dash='dash')
    ))
    
    fig_cumulative.add_hline(y=0, line_dash="dot", line_color="black")
    
    fig_cumulative.update_layout(
        title='Cumulative Financial Impact Over Time',
        xaxis_title='Months from Project Start',
        yaxis_title=f'Cumulative Value ({currency_symbol})',
        height=400
    )
    
    st.plotly_chart(fig_cumulative, use_container_width=True)

st.markdown("---")

# Implementation Timeline Chart
show_enhanced_timeline_section()

st.markdown("---")

# --- Value Reallocation & FTE Equivalency ---
st.subheader("🚀 Value Reallocation & FTE Equivalency")
col1, col2 = st.columns(2)

with col1:
    st.write(f"**Cost Available for Higher Margin Projects (Annually):** {currency_symbol}{total_operational_savings_from_time_saved:,.0f}")
    if effective_avg_fte_salary > 0:
        st.write(f"**Equivalent FTEs from Savings (Annually):** {equivalent_ftes_from_savings:,.1f} FTEs")
    else:
        st.write("Average FTE salary not provided, unable to calculate equivalent FTEs.")

with col2:
    if equivalent_ftes_from_savings > 0:
        st.metric("Strategic Capacity Gained", f"{equivalent_ftes_from_savings:.1f} FTEs")
        st.metric("Value per FTE Equivalent", f"{currency_symbol}{total_operational_savings_from_time_saved/equivalent_ftes_from_savings:,.0f}")

st.markdown("---")

# --- FOOTER AND METADATA ---
st.markdown("### 📋 Analysis Summary")

# Configuration summary
total_asset_mgmt_savings = asset_discovery_savings
config_summary = f"""
**Configuration Summary:**
- **Solution:** {solution_name}
- **Industry Template:** {selected_template}
- **Evaluation Period:** {evaluation_years} years
- **Currency:** {currency_symbol}
- **Discount Rate:** {discount_rate*100:.1f}%
- **Billing Start Month:** {billing_start_month}
- **Implementation Delay:** {implementation_delay_months} months
- **Benefits Ramp-up:** {benefits_ramp_up_months} months

**Results Summary:**
- **Expected NPV:** {currency_symbol}{scenario_results['Expected']['npv']:,.0f}
- **Expected ROI:** {scenario_results['Expected']['roi']*100:.1f}%
- **Payback Period:** {scenario_results['Expected']['payback_months']}
- **Annual Benefits:** {currency_symbol}{total_annual_benefits:,.0f}
- **Asset Discovery Value:** {currency_symbol}{total_asset_mgmt_savings:,.0f}
- **Equivalent FTEs from Savings:** {equivalent_ftes_from_savings:.1f} FTEs
"""

with st.expander("📊 View Complete Configuration Summary"):
    st.markdown(config_summary)

# Version and timestamp
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.caption("**Enhanced Business Value Assessment Tool v2.3** - Now with FTE Time Allocation")
with col2:
    st.caption(f"**Analysis generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Pro tips
st.info("💡 **Pro Tips:**")
st.markdown("""
- **NEW ✨ % of FTE Time**: Specify the percentage of time FTEs dedicate to a task for more accurate cost allocation.
- **🔍 Calculation Reasoning**: Use the Data Quality Dashboard to understand exactly how your numbers are calculated.
- **🚨 Red Flags**: The tool now validates if your workload exceeds the FTE time you've allocated.
- **Company Logo**: Upload your logo in the sidebar to create professional PDF executive summaries.
- **Export/Import**: Save configurations for future reference or stakeholder sharing.
""")

st.success("🎯 **Latest Enhancement**: This tool now includes inputs for FTE time allocation percentage, leading to more realistic cost calculations and smarter validation.")
