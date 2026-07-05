import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# ==========================================
# 🎨 页面基本配置
# ==========================================
st.set_page_config(
    page_title="连州玉竹栽培环境监测与水肥控制系统",
    page_icon="🌱",
    layout="wide"
)

# ==========================================
# 🔑 Supabase 配置凭证 (由底层设备数据源自动对齐)
# ==========================================
SUPABASE_URL = "https://srzfkhiminxmbrbdipay.supabase.co/rest/v1/base_env_data"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"

# ==========================================
# 📊 功能 1：Supabase 数据读取函数
# ==========================================
@st.cache_data(ttl=10) # 缓存10秒，避免频繁刷新撑爆云端免费流控
def fetch_env_data():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Range": "0-99" # 读取最新的100条数据记录用于图表展示
    }
    # 通过排序机制获取最新上传的生态环境数据
    params = {
        "order": "id.desc" 
    }
    try:
        response = requests.get(SUPABASE_URL, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            # 如果数据库有时间戳字段，可在此处转换为本地时间，否则使用递增 id 作为横轴
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at'])
            return df
        else:
            st.error(f"⚠️ 从 Supabase 读取数据失败，状态码: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ 数据库连接异常: {e}")
        return pd.DataFrame()

# ==========================================
# 🏛️ 系统大标题
# ==========================================
st.title("🌱 中山大学连州玉竹栽培环境监测与水肥控制系统")
st.markdown("---")

# ==========================================
# 🎛️ 侧边栏管理控制台
# ==========================================
with st.sidebar:
    st.header("⚙️ 系统控制台")
    auto_refresh = st.checkbox("🔄 开启数据自动刷新", value=True)
    refresh_interval = st.slider("⏱️ 刷新间隔 (秒)", min_value=5, max_value=60, value=10)
    
    st.markdown("---")
    st.subheader("📡 节点连通状态")
    st.success("🟢 环境采集节点 (ESP32-WiFi): 在线")
    
    # 预留第二块及第三块硬件单片机的状态指示接口
    st.info("🟡 水肥控制节点 (未连接): 等待配网...")
    st.info("🟡 视频观测节点 (未连接): 等待配网...")

# ==========================================
# 📊 核心功能展示区
# ==========================================
df_live = fetch_env_data()

if not df_live.empty:
    # 获取最新的单条环境传感器参数记录
    latest_record = df_live.iloc[0]
    
    # ---- 布局核心区块 1：实时生境监测指标 ----
    st.subheader("📈 连州种植基地：实时环境要素")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(label="☁️ 二氧化碳浓度", value=f"{int(latest_record.get('co2_ppm', 0))} ppm")
    with col2:
        st.metric(label="🌡️ 空气温度", value=f"{latest_record.get('air_temp', 0.0):.1f} °C")
    with col3:
        st.metric(label="💧 空气湿度", value=f"{latest_record.get('air_hum', 0.0):.1f} %")
    with col4:
        st.metric(label="☀️ 光照强度", value=f"{latest_record.get('light_lux', 0.0):.1f} lx")
    with col5:
        # 将土壤原始模拟量转化为直观的显示值
        st.metric(label="🌱 土壤水分含量", value=f"{int(latest_record.get('soil_moisture', 0))} %")

    st.markdown("---")

    # ---- 布局核心区块 2：水肥控制与实时视频（双列排版） ----
    left_col, right_col = st.columns([1, 1])

    with left_col:
        # 📊 功能 2：远程水肥继电器控制管理接口（预留接口）
        st.subheader("🚰 水肥一体化灌溉控制中心")
        st.markdown("针对连州玉竹根系栽培需求，在此对接第二块分布式继电器控制节点。")
        
        # 模拟电磁阀/水泵工作状态存储
        if 'pump_status' not in st.session_state:
            st.session_state.pump_status = False

        if st.session_state.pump_status:
            st.warning("⚠️ 当前状态：远程水泵正在运转，灌溉系统中...")
            if st.button("🔴 紧急关闭远程水泵"):
                # 🛠️ 【未来第二块单片机代码接入指引】:
                # 在此通过 requests.post() 向第二块板子的本地 WebServer，或是 MQTT/Supabase 的控制表发送“关泵”指令。
                st.session_state.pump_status = False
                st.rerun()
        else:
            st.success("🔵 当前状态：远程水泵处于静止/安全状态")
            if st.button("🟢 一键启动远程水灌溉"):
                # 🛠️ 【未来第二块单片机代码接入指引】:
                # 在此通过 requests.post() 发送“开泵”指令。
                st.session_state.pump_status = True
                st.rerun()
                
        # 硬件底层API接口框架说明
        with st.expander("🛠️ 第二块水肥单片机控制接口配置说明"):
            st.code("""
// 未来第二块板子通过轮询或 Webhook 接收此 Streamlit 的动作
// 接口调用框架示例：
// URL: https://your-api.com/control/pump
// Payload: {"action": "ON", "target_node": 2}
            """, language="json")

    with right_col:
        # 📊 功能 3：田间实时图像与视频观测系统（预留接口）
        st.subheader("📷 玉竹生态位田间实时视频")
        st.markdown("针对原产地生态环境与物候期跟踪，在此预留 ESP32-CAM 监控视频流。")
        
        # 视频回传组件占位
        st.image(
            "https://images.unsplash.com/photo-1628352081506-83c43123ed6d?auto=format&fit=crop&q=80&w=800", 
            caption="🎥 连州玉竹生态种植基地 - 模拟监视器画面 (待硬件上线后替换为实时视频流通道)"
        )
        
        with st.expander("🛠️ 第三块 ESP32-CAM 视频流接入说明"):
            st.markdown("""
            **视频流未来接入步骤：**
            1. 当你的 ESP32-CAM 单片机就位后，可以将其配置为局域网下的 `MJPEG` 视频流服务器。
            2. 获取单片机的内网或公网 IP 地址（例如 `http://192:168.x.x:81/stream`）。
            3. 将上方 `st.image()` 中的模拟 URL 替换为该设备的实时视频流网络地址，系统即可自动实现图像的高频动态刷新。
            """)

    # ---- 趋势数据历史图表可视化 ----
    st.markdown("---")
    st.subheader("📊 种植基地环境因子演变历史趋势 (最新100个采集周期数据)")
    
    # 抽取折线图所需数据集
    chart_data = df_live[['air_temp', 'air_hum', 'light_lux']].copy()
    st.line_chart(chart_data)

else:
    st.warning("⏳ 正在等待 Supabase 云端同步初始历史数据，请确保底层板子已成功连网发送首包。")

# ==========================================
# 🏢 落款与技术支持信息
# ==========================================
st.markdown("---")
st.markdown(
    "<center style='color:gray; font-size:14px;'>"
    "技术支持团队：中山大学农业与生物技术学院 魏蜜团队"
    "</center>", 
    unsafe_allow_html=True
)

# ==========================================
# ⏱️ 自动刷新控制逻辑
# ==========================================
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
