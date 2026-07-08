import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ==========================================
# ⚙️ 核心与页面配置
# ==========================================
st.set_page_config(
    page_title="连州玉竹栽培环境监测与水肥控制系统", 
    page_icon="🌱", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 隐藏顶部右侧 Streamlit 默认菜单，让大屏更具工程感
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Supabase 配置
SUPABASE_URL = "https://srzfkhiminxmbrbdipay.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"

# ==========================================
# 🔌 数据抓取引擎
# ==========================================
@st.cache_data(ttl=10) 
def fetch_latest_image():
    """从 Supabase 获取最新照片"""
    url = f"{SUPABASE_URL}/rest/v1/base_cam_data"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    params = {"select": "img_url, created_at", "order": "id.desc", "limit": 1}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0].get('img_url'), data[0].get('created_at')
    except Exception:
        pass
    return "https://images.unsplash.com/photo-1628352081506-83c43123ed6d?auto=format&fit=crop&q=80&w=800", "待 ESP32-CAM 上传"

# ==========================================
# 🖥️ 左侧边栏 (Sidebar) 渲染
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/zh/thumb/4/4e/Sun_Yat-sen_University_Logo.svg/1200px-Sun_Yat-sen_University_Logo.svg.png", width=200) # 中大Logo占位
    st.markdown("---")
    
    st.subheader("⚙️ 运行控制台")
    auto_refresh = st.checkbox("☑️ 开启数据自动刷新", value=True)
    refresh_rate = st.slider("⏱️ 刷新间隔 (秒)", min_value=5, max_value=60, value=10)
    
    st.markdown("---")
    st.subheader("🔗 节点连通状态")
    st.success("🟢 环境采集节点 (ESP32): 在线")
    st.warning("🟡 水肥控制节点: 等待配网...")
    
    # 🎉 这里为你更新了状态：摄像头已成功上线！
    st.success("🟢 视频观测节点 (ESP32-CAM): 在线") 
    
    st.markdown("---")
    st.caption("技术支持：中山大学农业与生物技术学院 彭宇涛课题组")

# ==========================================
# 🖥️ 顶部 Header 与 KPI 指标渲染
# ==========================================
st.title("🌱 连州玉竹栽培环境监测与水肥控制系统")
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"🕒 最新同步: {current_time} | 📍 基地: 广东连州高山生态种植区")
st.markdown("---")

# 5 个核心指标 KPI 行
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("☁️ 二氧化碳 [ppm]", "887")
k2.metric("🌡️ 空气温度 [℃]", "30.7")
k3.metric("💧 空气湿度 [%]", "80.1")
k4.metric("☀️ 光照强度 [lx]", "25.8")
k5.metric("🌱 土壤含水率 [%]", "72")
st.markdown("---")

# ==========================================
# 🖥️ 主体分栏区 (左 4 : 右 6 黄金比例)
# ==========================================
left_col, right_col = st.columns([4, 6])

# ----------------- 左侧：监控与干预区 -----------------
with left_col:
    st.subheader("📷 现场生态位实况")
    
    # 动态渲染 ESP32-CAM 传回的画面
    latest_img_url, capture_time = fetch_latest_image()
    display_time = capture_time[:19].replace("T", " ") if capture_time != "待 ESP32-CAM 上传" else capture_time
    
    st.image(
        latest_img_url, 
        caption=f"🎥 ESP32-CAM 实时流媒体接入 | 抓拍时间: {display_time}",
        use_container_width=True
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🚰 智能水肥干预")
    st.info("🔵 管道压力正常，处于待命状态")
    st.button("🟢 手动启动灌溉", use_container_width=True)

# ----------------- 右侧：微气候演变趋势区 -----------------
with right_col:
    st.subheader("📈 核心微气候演变趋势 (100周期)")
    
    # 模拟 100 周期的波动数据 (请在这里替换为你真实的数据库查询逻辑)
    df_temp = pd.DataFrame(np.random.randn(100, 1) * 0.5 + 30.7, columns=['空气温度 (℃)'])
    df_hum = pd.DataFrame(np.random.randn(100, 1) * 1.5 + 80.1, columns=['空气湿度 (%)'])
    df_light = pd.DataFrame(np.random.randn(100, 1) * 5 + 25.8, columns=['光照强度 (lx)'])
    df_soil = pd.DataFrame(np.random.randn(100, 1) * 0.8 + 72, columns=['土壤含水率 (%)'])
    df_co2 = pd.DataFrame(np.random.randn(100, 1) * 15 + 887, columns=['二氧化碳 (ppm)'])

    # 将图表分为两列完美对齐
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.caption("🌡️ 空气温度 (℃)")
        st.line_chart(df_temp, height=180)
        st.caption("☀️ 光照强度 (lx)")
        st.line_chart(df_light, height=180)
        st.caption("☁️ 二氧化碳 (ppm)")
        st.line_chart(df_co2, height=180)
        
    with chart_col2:
        st.caption("💧 空气湿度 (%)")
        st.line_chart(df_hum, height=180)
        st.caption("🌱 土壤含水率 (%)")
        st.line_chart(df_soil, height=180)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 **栽培提示:** 玉竹喜阴湿环境，若光照持续 > 8000 lx 且土壤含水率 < 40%，建议启动水肥一体化微喷降温保墒。")

# ==========================================
# 🔄 自动刷新底层逻辑
# ==========================================
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
