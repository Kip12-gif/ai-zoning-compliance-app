import io
import json
import streamlit as st
import geopandas as gpd
from shapely.geometry import shape, Polygon
import folium
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Land Parcel Zoning & Compliance Engine",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Land Parcel Zoning & Compliance Engine")
st.caption("Spatial Audit & Zoning Rule Evaluation System")

# ==========================================
# 2. BUILT-IN NAIROBI ZONING DATABASE
# ==========================================
@st.cache_data
def get_zoning_db():
    # Zone 1: Commercial Hub (Westlands / CBD Area)
    zone_cbd = Polygon([
        (36.810, -1.275), (36.835, -1.275), 
        (36.835, -1.295), (36.810, -1.295)
    ])
    
    # Zone 2: Residential Zone (Kilimani / Kileleshwa Area)
    zone_res = Polygon([
        (36.780, -1.280), (36.810, -1.280), 
        (36.810, -1.305), (36.780, -1.305)
    ])
    
    # Zone 3: High-Density Mixed Use Zone
    zone_mix = Polygon([
        (36.810, -1.295), (36.840, -1.295), 
        (36.840, -1.320), (36.810, -1.320)
    ])

    return gpd.GeoDataFrame({
        "zone_code": ["CBD-C1", "RES-R2", "MIX-MU3"],
        "zone_name": ["Nairobi Commercial Hub", "Low-Density Residential", "High-Density Mixed Use"],
        "max_building_height_m": [45.0, 15.0, 30.0],
        "max_ground_coverage_pct": [80.0, 40.0, 65.0],
        "permitted_uses": [
            ["Retail / Commercial", "Multi-Family Residential", "Industrial"],
            ["Single-Family Residential", "Multi-Family Residential"],
            ["Single-Family Residential", "Multi-Family Residential", "Retail / Commercial"]
        ],
        "geometry": [zone_cbd, zone_res, zone_mix]
    }, crs="EPSG:4326")

# ==========================================
# 3. SPATIAL MAP RENDERER (SATELLITE & TOPO)
# ==========================================
def render_spatial_map(zoning_gdf, parcel_polygon):
    centroid = parcel_polygon.centroid
    
    # Base Map Initialization
    m = folium.Map(
        location=[centroid.y, centroid.x], 
        zoom_start=15, 
        tiles=None  # Standard tiles turned off to add custom tile layers
    )

    # 1. OpenStreetMap (Standard Street View)
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Street Map",
        control=True
    ).add_to(m)

    # 2. Esri World Imagery (Satellite)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satellite Imagery",
        overlay=False,
        control=True
    ).add_to(m)

    # 3. OpenTopoMap (Topographic)
    folium.TileLayer(
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr="OpenTopoMap",
        name="Topographic Map",
        overlay=False,
        control=True
    ).add_to(m)

    # Zoning Boundary Layer
    folium.GeoJson(
        zoning_gdf,
        name="Zoning Boundaries",
        style_function=lambda feature: {
            "fillColor": "#3182bd" if feature["properties"]["zone_code"] == "RES-R2" else (
                "#e6550d" if feature["properties"]["zone_code"] == "CBD-C1" else "#31a354"
            ),
            "color": "black",
            "weight": 2,
            "fillOpacity": 0.3
        },
        tooltip=folium.GeoJsonTooltip(fields=["zone_code", "zone_name"], aliases=["Zone Code:", "Zone Name:"])
    ).add_to(m)

    # Target Parcel Layer
    parcel_gdf = gpd.GeoDataFrame([{"geometry": parcel_polygon}], crs="EPSG:4326")
    folium.GeoJson(
        parcel_gdf,
        name="Target Parcel",
        style_function=lambda feature: {
            "fillColor": "#de2d26",
            "color": "red",
            "weight": 3,
            "fillOpacity": 0.55
        },
        tooltip="Uploaded Parcel Boundary"
    ).add_to(m)

    # Layer Control Switcher
    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    return m

# ==========================================
# 4. COMPLIANCE RULE ENGINE
# ==========================================
def evaluate_compliance(parcel_polygon, proposed_use, height, coverage, zoning_gdf):
    parcel_gdf = gpd.GeoDataFrame([{"geometry": parcel_polygon}], crs="EPSG:4326")
    
    # Spatial Intersection Check
    intersected = gpd.sjoin(parcel_gdf, zoning_gdf, how="inner", predicate="intersects")
    
    if intersected.empty:
        return None, {"status": "ERROR", "message": "Uploaded parcel boundary falls outside designated zoning coverage."}
    
    matched_zone = intersected.iloc[0]
    checks = {}
    
    # 1. Height Check
    max_h = matched_zone["max_building_height_m"]
    checks["height"] = {
        "passed": height <= max_h,
        "proposed": f"{height} m",
        "allowed": f"{max_h} m"
    }
    
    # 2. Coverage Check
    max_cov = matched_zone["max_ground_coverage_pct"]
    checks["coverage"] = {
        "passed": coverage <= max_cov,
        "proposed": f"{coverage}%",
        "allowed": f"{max_cov}%"
    }
    
    # 3. Land Use Check
    allowed_uses = matched_zone["permitted_uses"]
    checks["use"] = {
        "passed": proposed_use in allowed_uses,
        "proposed": proposed_use,
        "allowed": ", ".join(allowed_uses)
    }
    
    overall_passed = all([checks["height"]["passed"], checks["coverage"]["passed"], checks["use"]["passed"]])
    
    return matched_zone, {
        "overall_passed": overall_passed,
        "checks": checks
    }

# ==========================================
# 5. PDF REPORT GENERATOR
# ==========================================
def generate_pdf_report(parcel_id, area_ha, zone_info, audit_results):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "OFFICIAL ZONING AUDIT CERTIFICATE")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.line(50, 725, 550, 725)
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 700, f"Parcel Reference: {parcel_id}")
    c.drawString(50, 680, f"Calculated Area: {area_ha:.3f} Hectares")
    c.drawString(50, 660, f"Designated Zone: {zone_info['zone_code']} - {zone_info['zone_name']}")
    
    status_str = "COMPLIANT / APPROVED" if audit_results["overall_passed"] else "NON-COMPLIANT"
    c.setFillColorRGB(0, 0.5, 0) if audit_results["overall_passed"] else c.setFillColorRGB(0.8, 0, 0)
    c.drawString(50, 630, f"AUDIT STATUS: {status_str}")
    
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 590, "Parameter Compliance Summary:")
    
    y = 560
    c.setFont("Helvetica", 10)
    for key, data in audit_results["checks"].items():
        pass_text = "PASS" if data["passed"] else "FAIL"
        c.drawString(60, y, f"• {key.upper()}: {pass_text} | Proposed: {data['proposed']} | Allowed Limit: {data['allowed']}")
        y -= 25
        
    c.save()
    buffer.seek(0)
    return buffer

# ==========================================
# 6. USER INTERFACE & APP LAYOUT
# ==========================================
zoning_gdf = get_zoning_db()

# Default Sample Parcel Polygon
default_parcel = Polygon([
    (36.815, -1.282), (36.818, -1.282), 
    (36.818, -1.285), (36.815, -1.285)
])

col1, col2 = st.columns([1.1, 0.9])

with col1:
    st.subheader("1. Spatial Parcel Input")
    
    uploaded_file = st.file_uploader(
        "Upload Parcel File (.geojson or .json)", 
        type=["geojson", "json"],
        help="Upload a GeoJSON file containing a Polygon geometry."
    )
    
    target_parcel = default_parcel
    
    if uploaded_file is not None:
        try:
            geojson_data = json.load(uploaded_file)
            
            if geojson_data.get("type") == "FeatureCollection":
                geom_dict = geojson_data["features"][0]["geometry"]
            elif geojson_data.get("type") == "Feature":
                geom_dict = geojson_data["geometry"]
            else:
                geom_dict = geojson_data
                
            target_parcel = shape(geom_dict)
            st.success("✅ GeoJSON loaded successfully!")
        except Exception as e:
            st.error(f"Error parsing GeoJSON: {e}. Reverting to default sample parcel.")
            target_parcel = default_parcel

    # Area Calculation using EPSG:3857 (Metric Projection)
    parcel_gdf = gpd.GeoDataFrame([{"geometry": target_parcel}], crs="EPSG:4326")
    area_sqm = parcel_gdf.to_crs(epsg=3857).geometry.area.iloc[0]
    area_ha = area_sqm / 10000.0
    
    st.info(f"📐 **Computed Parcel Area:** {area_sqm:,.1f} m² ({area_ha:.3f} Ha)")

    st.subheader("2. Proposed Development Parameters")
    parcel_id = st.text_input("Parcel Reference / LR Number", "LR-209/18250")
    
    proposed_use = st.selectbox(
        "Proposed Land Use", 
        ["Single-Family Residential", "Multi-Family Residential", "Retail / Commercial", "Industrial"]
    )
    proposed_height = st.number_input("Building Height (meters)", value=12.0, min_value=1.0, max_value=100.0, step=1.0)
    proposed_coverage = st.slider("Ground Coverage (%)", 10, 100, 35)

    run_audit = st.button("🔍 Execute Compliance Audit", type="primary", use_container_width=True)

    if run_audit:
        matched_zone, audit_results = evaluate_compliance(
            target_parcel, proposed_use, proposed_height, proposed_coverage, zoning_gdf
        )
        
        st.divider()
        st.subheader("3. Audit Results")
        
        if audit_results.get("status") == "ERROR":
            st.error(audit_results["message"])
        else:
            if audit_results["overall_passed"]:
                st.success(f"✅ APPROVED: Proposal satisfies all parameters for {matched_zone['zone_code']} ({matched_zone['zone_name']}).")
            else:
                st.error(f"❌ NON-COMPLIANT: Proposal violates regulations for {matched_zone['zone_code']} ({matched_zone['zone_name']}).")
            
            res_data = []
            for param, details in audit_results["checks"].items():
                res_data.append({
                    "Parameter": param.capitalize(),
                    "Status": "✅ PASS" if details["passed"] else "❌ FAIL",
                    "Proposed": details["proposed"],
                    "Allowed Limit": details["allowed"]
                })
            
            st.table(res_data)
            
            pdf_bytes = generate_pdf_report(parcel_id, area_ha, matched_zone, audit_results)
            st.download_button(
                label="📄 Download Official Compliance Certificate (PDF)",
                data=pdf_bytes,
                file_name=f"zoning_audit_{parcel_id.replace('/', '_')}.pdf",
                mime="application/pdf"
            )

with col2:
    st.subheader("Spatial Overlay & Boundary Verification")
    st.caption("Use the layer control in the top-right corner to toggle Satellite or Topo basemaps.")
    m = render_spatial_map(zoning_gdf, target_parcel)
    st.components.v1.html(m._repr_html_(), height=620)
