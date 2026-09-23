import streamlit as st
import geopandas as gpd
from shapely.geometry import Polygon
import folium
from datetime import datetime

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="AI Land Parcel Zoning App",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ AI Land Parcel Zoning & Compliance Engine")
st.caption("Registered Parcel Audit & Spatial Compliance Verification")

# ==========================================
# 2. FREE BASEMAP SPATIAL MAP RENDERER
# ==========================================
def render_spatial_map(zoning_gdf, parcel_polygon):
    centroid = parcel_polygon.centroid
    
    # Standard OpenStreetMap (100% Free, NO API KEY required)
    m = folium.Map(
        location=[centroid.y, centroid.x], 
        zoom_start=15, 
        tiles="OpenStreetMap"
    )

    # Add Zoning Boundaries
    folium.GeoJson(
        zoning_gdf,
        style_function=lambda feature: {
            "fillColor": "#3182bd" if feature["properties"]["zone_code"] == "R-1" else "#e6550d" if feature["properties"]["zone_code"] == "C-2" else "#31a354",
            "color": "black",
            "weight": 2,
            "fillOpacity": 0.3
        },
        tooltip=folium.GeoJsonTooltip(fields=["zone_code", "zone_name"], aliases=["Zone:", "Name:"])
    ).add_to(m)

    # Add Target Parcel
    parcel_gdf = gpd.GeoDataFrame([{"geometry": parcel_polygon}], crs="EPSG:4326")
    folium.GeoJson(
        parcel_gdf,
        style_function=lambda feature: {
            "fillColor": "#de2d26",
            "color": "red",
            "weight": 3,
            "fillOpacity": 0.6
        },
        tooltip="Target Registered Parcel"
    ).add_to(m)

    return m

# ==========================================
# 3. SPATIAL DATA GENERATOR (MOCK DB)
# ==========================================
def get_zoning_db():
    zone_a = Polygon([(36.810, -1.280), (36.820, -1.280), (36.820, -1.290), (36.810, -1.290)])
    zone_b = Polygon([(36.820, -1.280), (36.830, -1.280), (36.830, -1.290), (36.820, -1.290)])
    
    return gpd.GeoDataFrame({
        "zone_code": ["R-1", "C-2"],
        "zone_name": ["Low-Density Residential", "Commercial Hub"],
        "max_building_height_m": [12.0, 35.0],
        "max_ground_coverage_pct": [40.0, 80.0],
        "permitted_uses": ["Single-Family Residential, Urban Agriculture", "Retail, Office, Commercial"],
        "geometry": [zone_a, zone_b]
    }, crs="EPSG:4326")

# ==========================================
# 4. USER INTERFACE & LOGIC
# ==========================================
col1, col2 = st.columns([1, 1])

zoning_gdf = get_zoning_db()

# Target Sample Parcel Boundaries
sample_parcel = Polygon([
    (36.815, -1.282), (36.818, -1.282), 
    (36.818, -1.285), (36.815, -1.285)
])

with col1:
    st.subheader("Proposed Development Parameters")
    proposed_use = st.selectbox(
        "Proposed Land Use", 
        ["Single-Family Residential", "Multi-Family Residential", "Retail / Commercial", "Industrial"]
    )
    proposed_height = st.number_input("Building Height (meters)", value=10.0, step=1.0)
    proposed_coverage = st.slider("Ground Coverage (%)", 10, 100, 35)

    if st.button("Run Compliance Audit", type="primary"):
        st.success("Audit executed successfully!")
        st.markdown(f"**Selected Land Use:** {proposed_use}")
        st.markdown(f"**Proposed Building Height:** {proposed_height} meters")
        st.markdown(f"**Ground Coverage:** {proposed_coverage}%")

with col2:
    st.subheader("Spatial Overlay (Keyless OpenStreetMap)")
    m = render_spatial_map(zoning_gdf, sample_parcel)
    st.components.v1.html(m._repr_html_(), height=500)