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
    page_title="AI Land Parcel Zoning App",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ AI Land Parcel Zoning & Compliance Engine")
st.caption("Upload Parcel GeoJSON & Run Spatial Compliance Audit")

# ==========================================
# 2. SPATIAL DATA GENERATOR (MOCK ZONING DB)
# ==========================================
@st.cache_data
def get_zoning_db():
    # Zone A: Low-Density Residential (R-1)
    zone_a = Polygon([(36.810, -1.280), (36.820, -1.280), (36.820, -1.290), (36.810, -1.290)])
    # Zone B: Commercial Hub (C-2)
    zone_b = Polygon([(36.820, -1.280), (36.830, -1.280), (36.830, -1.290), (36.820, -1.290)])
    
    return gpd.GeoDataFrame({
        "zone_code": ["R-1", "C-2"],
        "zone_name": ["Low-Density Residential", "Commercial Hub"],
        "max_building_height_m": [12.0, 35.0],
        "max_ground_coverage_pct": [40.0, 80.0],
        "permitted_uses": [
            ["Single-Family Residential", "Urban Agriculture"], 
            ["Retail / Commercial", "Multi-Family Residential", "Industrial"]
        ],
        "geometry": [zone_a, zone_b]
    }, crs="EPSG:4326")

# ==========================================
# 3. SPATIAL MAP RENDERER
# ==========================================
def render_spatial_map(zoning_gdf, parcel_polygon):
    centroid = parcel_polygon.centroid
    m = folium.Map(
        location=[centroid.y, centroid.x], 
        zoom_start=16, 
        tiles="OpenStreetMap"
    )

    # Zoning Layer
    folium.GeoJson(
        zoning_gdf,
        style_function=lambda feature: {
            "fillColor": "#3182bd" if feature["properties"]["zone_code"] == "R-1" else "#e6550d",
            "color": "black",
            "weight": 2,
            "fillOpacity": 0.25
        },
        tooltip=folium.GeoJsonTooltip(fields=["zone_code", "zone_name"], aliases=["Zone:", "Name:"])
    ).add_to(m)

    # Target Parcel Layer
    parcel_gdf = gpd.GeoDataFrame([{"geometry": parcel_polygon}], crs="EPSG:4326")
    folium.GeoJson(
        parcel_gdf,
        style_function=lambda feature: {
            "fillColor": "#de2d26",
            "color": "red",
            "weight": 3,
            "fillOpacity": 0.5
        },
        tooltip="Uploaded Parcel Boundary"
    ).add_to(m)

    return m

# ==========================================
# 4. COMPLIANCE RULE ENGINE
# ==========================================
def evaluate_compliance(parcel_polygon, proposed_use, height, coverage, zoning_gdf):
    parcel_gdf = gpd.GeoDataFrame([{"geometry": parcel_polygon}], crs="EPSG:4326")
    
    # Spatial Join / Intersection
    intersected = gpd.sjoin(parcel_gdf, zoning_gdf, how="inner", predicate="intersects")
    
    if intersected.empty:
        return None, {"status": "ERROR", "message": "Uploaded parcel boundary falls outside known zoning coverage."}
    
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
    c.drawString(50, 750, "ZONING COMPLIANCE AUDIT REPORT")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.line(50, 725, 550, 725)
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 700, f"Parcel Identification: {parcel_id}")
    c.drawString(50, 680, f"Calculated Area: {area_ha:.3f} Hectares")
    c.drawString(50, 660, f"Designated Zone: {zone_info['zone_code']} - {zone_info['zone_name']}")
    
    status_str = "APPROVED" if audit_results["overall_passed"] else "NON-COMPLIANT"
    c.setFillColorRGB(0, 0.5, 0) if audit_results["overall_passed"] else c.setFillColorRGB(0.8, 0, 0)
    c.drawString(50, 630, f"AUDIT STATUS: {status_str}")
    
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 590, "Detailed Rule Evaluation:")
    
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

# Default Fallback Sample Parcel
default_parcel = Polygon([
    (36.815, -1.282), (36.818, -1.282), 
    (36.818, -1.285), (36.815, -1.285)
])

col1, col2 = st.columns([1.1, 0.9])

with col1:
    st.subheader("1. Parcel Boundary Input")
    
    uploaded_file = st.file_uploader(
        "Upload Parcel File (.geojson or .json)", 
        type=["geojson", "json"],
        help="Upload a GeoJSON file containing a Polygon geometry for your parcel."
    )
    
    target_parcel = default_parcel
    
    if uploaded_file is not None:
        try:
            geojson_data = json.load(uploaded_file)
            
            # Extract geometry from FeatureCollection or single Feature
            if geojson_data.get("type") == "FeatureCollection":
                geom_dict = geojson_data["features"][0]["geometry"]
            elif geojson_data.get("type") == "Feature":
                geom_dict = geojson_data["geometry"]
            else:
                geom_dict = geojson_data
                
            target_parcel = shape(geom_dict)
            st.success("✅ GeoJSON loaded successfully!")
        except Exception as e:
            st.error(f"Error reading GeoJSON: {e}. Reverting to default sample parcel.")
            target_parcel = default_parcel

    # Calculate Area dynamically using EPSG:3857 (World Mercator)
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
    proposed_height = st.number_input("Building Height (meters)", value=10.0, min_value=1.0, max_value=100.0, step=1.0)
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
                st.success(f"✅ APPROVED: Development complies with {matched_zone['zone_code']} ({matched_zone['zone_name']}) regulations.")
            else:
                st.error(f"❌ NON-COMPLIANT: Proposal violates {matched_zone['zone_code']} ({matched_zone['zone_name']}) rules.")
            
            # Displays detailed status table
            res_data = []
            for param, details in audit_results["checks"].items():
                res_data.append({
                    "Parameter": param.capitalize(),
                    "Status": "✅ PASS" if details["passed"] else "❌ FAIL",
                    "Proposed": details["proposed"],
                    "Allowed Limit": details["allowed"]
                })
            
            st.table(res_data)
            
            # PDF Generation & Download
            pdf_bytes = generate_pdf_report(parcel_id, area_ha, matched_zone, audit_results)
            st.download_button(
                label="📄 Download Official Certificate (PDF)",
                data=pdf_bytes,
                file_name=f"zoning_audit_{parcel_id.replace('/', '_')}.pdf",
                mime="application/pdf"
            )

with col2:
    st.subheader("Spatial Overlay & Boundary Verification")
    m = render_spatial_map(zoning_gdf, target_parcel)
    st.components.v1.html(m._repr_html_(), height=600)(m._repr_html_(), height=500)
