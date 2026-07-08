import streamlit as st
import requests
from datetime import datetime

# ==========================================
# ⚙️ 核心配置区
# ==========================================
st.set_page_config(
    page_title="连州玉竹基地 IoT 大屏", 
    page_icon="🌱", 
    layout="wide"
)

# 你的 Supabase 专属配置
SUPABASE_URL = "https://srzfkhiminxmbrbdipay.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"

# ==========================================
# 🔌 数据抓取引擎
# ==========================================
@st.cache_data(ttl=10) # 缓存10秒，每10秒自动去云端查一次最新照片
def fetch_latest_image():
    """从 Supabase 的 base_cam_data 表获取最新上传的田间照片"""
    url = f"{SUPABASE_URL}/rest/v1/base_cam_data"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    # 查询参数：只要 img_url 字段，按 id 倒序排列，只取第 1 条（即最新的一条）
    params = {
        "select": "img_url, created_at",
        "order": "id.desc",
        "limit": 1
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                # 成功拿到最新的图片链接
                return data[0].get('img_url'), data[0].get('created_at')
    except Exception as e:
        st.sidebar.error(f"网络请求报错: {e}")
        
    # 如果没查到数据或报错，返回一张默认的错误占位图
    return "https://images.unsplash.com/photo-1628352081506-83c43123ed6d?auto=format&fit=crop&q=80&w=800", "未知时间"

# ==========================================
# 🖥️ 大屏 UI 渲染区
# ==========================================
st.title("🌱 连州玉竹生态种植基地 - 微气候与实况监控大屏")
st.markdown("---")

# 将页面分为左右两栏
left_col, right_col = st.columns([1, 1])

# ----------------- 左侧：环境数据区 -----------------
with left_col:
    st.subheader("📊 实时环境数据 (LILYGO 节点)")
    
    # ⚠️ 【注意】这里保留你原本获取和展示温湿度折线图的代码
    st.info("环境温湿度、CO2 等折线图表将在这里展示...")
    # st.line_chart(...) 


# ----------------- 右侧：视频抓拍区 -----------------
with right_col:
    st.subheader("📷 生态位田间实况 (ESP32-CAM 节点)")
    
    # 动态抓取最新图片链接
    latest_img_url, capture_time = fetch_latest_image()
    
    # 格式化时间显示 (可选，将 UTC 时间转为更易读的格式)
    display_time = capture_time[:19].replace("T", " ") if capture_time != "未知时间" else capture_time
    
    # 渲染图片
    st.image(
        latest_img_url, 
        caption=f"🎥 现场实况 | 抓拍时间: {display_time} | 每 10 秒自动检查更新",
        use_container_width=True
    )
