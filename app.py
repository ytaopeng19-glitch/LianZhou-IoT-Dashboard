import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# ==========================================
# 🎨 页面基本配置与全局 CSS 压缩 (专为 27寸大屏优化)
# ==========================================
st.set_page_config(
    page_title="连州玉竹栽培环境监测与水肥控制系统",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入 CSS：压缩四周留白，缩小字体，强制图表紧凑
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }
    /* 缩小标题间距 */
    h1, h2, h3 { margin-bottom: 0.1rem !important; padding-bottom: 0.1rem !important; }
    /* 紧凑化指标卡片数字大小 */
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    /* 隐藏 Streamlit 默认的顶部菜单和底部水印 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🔑 Supabase 配置凭证
# ==========================================
SUPABASE_URL = "https://srzfkhiminxmbrbdipay.supabase.co/rest/v1/base_env_data"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"

# ==========================================
# 📊 功能 1：Supabase 数据读取函数
# ==========================================
@st.cache_data(ttl=10)
def fetch_env_data():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Range": "0-99"
    }
    params = {"order": "id.desc"}
    try:
        response = requests.get(SUPABASE_URL, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at'])
                if df['created_at'].dt.tz is None:
                    df['created_at'] = df['created_at'].dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
                else:
                    df['created_at'] = df['created_at'].dt.tz_convert('Asia/Shanghai')
            return df
        else:
            st.error(f"⚠️ 数据读取失败，状态码: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ 数据库连接异常: {e}")
        return pd.DataFrame()

@st.cache_data
def convert_df_to_csv(df):
    export_df = df.copy()
    if 'created_at' in export_df.columns:
        export_df['created_at'] = export_df['created_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
    columns_mapping = {
        "id": "数据编号",
        "created_at": "采集时间(北京时间24H)",
        "co2_ppm": "二氧化碳浓度(ppm)",
        "air_temp": "空气温度(°C)",
        "air_hum": "空气湿度(%)",
        "light_lux": "光照强度(lx)",
        "soil_moisture": "土壤含水率(%)"
    }
    existing_mapping = {k: v for k, v in columns_mapping.items() if k in export_df.columns}
    export_df = export_df.rename(columns=existing_mapping)
    ordered_cols = [v for v in columns_mapping.values() if v in export_df.columns]
    export_df = export_df[ordered_cols]
    return export_df.to_csv(index=False).encode('utf-8-sig')

# ==========================================
# 🎛️ 侧边栏：品牌 Logo 与 控制台
# ==========================================
with st.sidebar:
    # 插入学院 Logo
    try:
        st.image("logo绿色.png", use_container_width=True)
    except Exception:
        st.warning("⚠️ 未找到 logo绿色.png，请确保图片在同级目录下。")
        
    st.markdown("---")
    st.header("⚙️ 运行控制台")
    auto_refresh = st.checkbox("🔄 开启数据自动刷新", value=True)
    refresh_interval = st.slider("⏱️ 刷新间隔 (秒)", 5, 60, 10)
    
    st.markdown("---")
    st.subheader("📡 节点连通状态")
    st.success("🟢 环境采集节点 (ESP32): 在线")
    st.info("🟡 水肥控制节点: 等待配网...")
    st.info("🟡 视频观测节点: 等待配网...")
    
    st.markdown("---")
    st.markdown("<center style='color:gray; font-size:12px;'>技术支持：中山大学农业与生物技术学院 魏蜜团队</center>", unsafe_allow_html=True)

# ==========================================
# 🏛️ 主界面：标题与导出按钮同行显示
# ==========================================
df_live = fetch_env_data()

head_col1, head_col2 = st.columns([5, 1])
with head_col1:
    st.title("🌱 连州玉竹栽培环境监测与水肥控制系统")
    if not df_live.empty:
        latest_time_str = df_live.iloc[0]['created_at'].strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"🕒 最新同步：**{latest_time_str}** | 基地：广东连州高山生态种植区")
with head_col2:
    if not df_live.empty:
        csv_bytes = convert_df_to_csv(df_live)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        st.download_button(
            label="📥 导出数据",
            data=csv_bytes,
            file_name=f"连州环境数据_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True
        )

# ==========================================
# 📊 核心指标卡片区 (横向紧凑排列)
# ==========================================
if not df_live.empty:
    latest_record = df_live.iloc[0]
    
    # 使用自定义高亮容器包裹指标
    st.markdown("<div style='background-color: #f8f9fa; padding: 10px; border-radius: 10px; margin-bottom: 15px;'>", unsafe_allow_html=True)
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    m_col1.metric("☁️ 二氧化碳 (ppm)", f"{int(latest_record.get('co2_ppm', 0))}")
    m_col2.metric("🌡️ 空气温度 (°C)", f"{latest_record.get('air_temp', 0.0):.1f}")
    m_col3.metric("💧 空气湿度 (%)", f"{latest_record.get('air_hum', 0.0):.1f}")
    m_col4.metric("☀️ 光照强度 (lx)", f"{latest_record.get('light_lux', 0.0):.1f}")
    m_col5.metric("🌱 土壤含水率 (%)", f"{int(latest_record.get('soil_moisture', 0))}")
    st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================
    # 🖥️ 全景大屏非对称布局：30% 视频+控制 | 70% 历史趋势图
    # ==========================================
    main_left, main_right = st.columns([3, 7], gap="large")

    # ----- 左侧：现场实况与硬件干预 -----
    with main_left:
        st.subheader("📷 现场生态位实况")
        st.image(
            "https://images.unsplash.com/photo-1628352081506-83c43123ed6d?auto=format&fit=crop&q=80&w=800", 
            caption="待 ESP32-CAM 上线后接入流媒体"
        )
        
        st.subheader("🚰 智能水肥干预")
        if 'pump_status' not in st.session_state:
            st.session_state.pump_status = False

        if st.session_state.pump_status:
            st.error("⚠️ 滴灌系统正在运行中...")
            if st.button("🔴 紧急切断水泵", use_container_width=True):
                st.session_state.pump_status = False
                st.rerun()
        else:
            st.success("🔵 管道压力正常，处于待命状态")
            if st.button("🟢 手动启动灌溉", use_container_width=True):
                st.session_state.pump_status = True
                st.rerun()

    # ----- 右侧：高密度图表矩阵 -----
    with main_right:
        st.subheader("📈 核心微气候演变趋势 (100周期)")
        
        chart_df = df_live[['created_at', 'air_temp', 'air_hum', 'light_lux', 'co2_ppm', 'soil_moisture']].copy()
        chart_df.set_index('created_at', inplace=True)
        
        # 将图表放入 2 列网格中，并严格限制图表高度 (height=180)
        c_col1, c_col2 = st.columns(2)
        
        with c_col1:
            st.caption("🌡️ 空气温度 (°C)")
            st.line_chart(chart_df[['air_temp']], height=180)
            
            st.caption("☀️ 光照强度 (lx)")
            st.line_chart(chart_df[['light_lux']], height=180)
            
            st.caption("☁️ 二氧化碳 (ppm)")
            st.line_chart(chart_df[['co2_ppm']], height=180)

        with c_col2:
            st.caption("💧 空气湿度 (%)")
            st.line_chart(chart_df[['air_hum']], height=180)
            
            st.caption("🌱 土壤含水率 (%)")
            st.line_chart(chart_df[['soil_moisture']], height=180)
            
            # 补齐右下角空白，提升UI平衡感
            st.info("💡 **栽培提示**：玉竹喜阴湿环境，若光照持续 > 8000 lx 且土壤含水率 < 40%，建议启动水肥一体化微喷降温保墒。")

else:
    st.warning("⏳ 正在建立与野外基站的下行链路，请检查供电与网络环境...")

# ==========================================
# ⏱️ 自动刷新控制逻辑
# ==========================================
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
