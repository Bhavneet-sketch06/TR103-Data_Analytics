import streamlit as st


# ==========================================================
# SECTION HEADER
# ==========================================================

def section_header(title, subtitle):

    st.markdown(
        f"""
<div style="
padding:8px 0px 20px 0px;
">

<h2 style="
margin-bottom:6px;
">
{title}
</h2>

<p style="
font-size:16px;
opacity:0.75;
margin-top:0;
">
{subtitle}
</p>

</div>
""",
        unsafe_allow_html=True,
    )


# ==========================================================
# INSIGHT CARD
# ==========================================================

def insight_card(icon, title, value, description):

    st.markdown(
        f"""
<div style="
background: var(--secondary-background-color);
padding:22px;
border-radius:18px;
border-left:6px solid #2563EB;
box-shadow:0px 6px 18px rgba(0,0,0,0.08);
height:190px;
">

<div style="
font-size:34px;
margin-bottom:12px;
">
{icon}
</div>

<div style="
font-size:18px;
font-weight:700;
margin-bottom:10px;
">
{title}
</div>

<div style="
font-size:30px;
font-weight:800;
margin-bottom:12px;
">
{value}
</div>

<div style="
opacity:0.75;
font-size:15px;
line-height:1.6;
">
{description}
</div>

</div>
""",
        unsafe_allow_html=True,
    )