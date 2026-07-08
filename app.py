import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import time
import base64          
from io import BytesIO 
from PIL import Image  

# ==========================================
# ⚙️ 核心与时区配置
# ==========================================
# 强制锁定北京时间 (UTC+8)，无视服务器本地时区
BEIJING_TZ = timezone(timedelta(hours=8))

st.set_page_config(
    page_title="连州玉竹栽培环境监测与水肥控制系统", 
    page_icon="🌱", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 隐藏顶部右侧 Streamlit 默认菜单
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

SUPABASE_URL = "https://srzfkhiminxmbrbdipay.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"

# ==========================================
# 🔌 数据抓取与智能决策引擎
# ==========================================
@st.cache_data(ttl=10) 
def fetch_latest_image():
    """从 Supabase 获取最新照片URL"""
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

@st.cache_data(ttl=3600, max_entries=20) 
def process_and_rotate_image(img_url, rotation_angle):
    """下载图片并进行角度旋转，转换为 Base64 供 HTML 渲染"""
    if not img_url.startswith("http"):
        return img_url
    try:
        resp = requests.get(img_url, timeout=5)
        if resp.status_code == 200:
            img = Image.open(BytesIO(resp.content))
            if rotation_angle != 0:
                img = img.rotate(-rotation_angle, expand=True)
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            img_b64 = base64.b64encode(buffered.getvalue()).decode()
            return f"data:image/jpeg;base64,{img_b64}"
    except Exception:
        pass
    return img_url 

@st.cache_data(ttl=5)
def fetch_latest_env_data():
    """
    读取 LILYGO 节点的环境数据 
    目前以大屏系统时间为准模拟产生最新戳，后续接入真实数据表后替换为数据库时间
    """
    return {
        "co2": 887,
        "temp": 30.7,
        "humidity": 80.1,
        "light": 25.8,
        "soil_moisture": 60,  
        "timestamp": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S") # 动态绑定北京时间戳
    }

# ==========================================
# 🖥️ 左侧边栏 (Sidebar) 渲染
# ==========================================
with st.sidebar:
    try:
        st.image("logo绿色.png", use_container_width=True)
    except Exception:
        st.error("未能找到 logo绿色.png 文件")
        
    st.markdown("---")
    
    st.subheader("⚙️ 运行控制台")
    auto_refresh = st.checkbox("☑️ 开启数据自动刷新", value=True)
    refresh_rate = st.slider("⏱️ 刷新间隔 (秒)", min_value=5, max_value=60, value=10)
    
    cam_rotation = st.selectbox("🔄 画面校正角度 (顺时针)", [0, 90, 180, 270], index=0, format_func=lambda x: f"{x}°")
    
    st.markdown("---")
    st.subheader("🔗 节点连通状态")
    st.success("🟢 环境采集节点 (LILYGO): 在线")
    st.success("🟢 水肥控制节点 (ESP32-C3): 在线联控中")
    st.success("🟢 视频观测节点 (ESP32-CAM): 在线") 
    
    st.markdown("---")
    st.caption("技术支持：中山大学农业与生物技术学院 彭宇涛课题组")

# ==========================================
# 🖥️ 顶部 Header 与 KPI 指标渲染
# ==========================================
st.title("🌱 连州玉竹栽培环境监测与水肥控制系统")

# 🌟 大屏主系统北京时间
current_sys_time = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"💻 大屏系统时间 (北京时间): {current_sys_time} | 📍 基地: 广东连州高山生态种植区")
st.markdown("---")

# 获取节点环境数据
env_data = fetch_latest_env_data()

# 🌟 新增：独立显示环境节点的数据更新时间
st.markdown(f"**📡 环境节点 (LILYGO) 数据同步时间:** `{env_data['timestamp']}`")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("☁️ 二氧化碳 [ppm]", f"{env_data['co2']}")
k2.metric("🌡️ 空气温度 [℃]", f"{env_data['temp']}")
k3.metric("💧 空气湿度 [%]", f"{env_data['humidity']}")
k4.metric("☀️ 光照强度 [lx]", f"{env_data['light']}")
k5.metric("🌱 土壤含水率 [%]", f"{env_data['soil_moisture']}")
st.markdown("---")

# ==========================================
# 🖥️ 主体分栏区
# ==========================================
left_col, right_col = st.columns([4, 6])

# ----------------- 左侧：监控与干预区 -----------------
with left_col:
    st.subheader("📷 现场生态位实况")
    
    latest_img_url, capture_time = fetch_latest_image()
    
    # 时区转换：ESP32-CAM 传上来的云端时间转北京时间
    if capture_time != "待 ESP32-CAM 上传":
        try:
            dt_beijing = pd.to_datetime(capture_time).tz_convert('Asia/Shanghai')
            display_time = dt_beijing.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            display_time = capture_time[:19].replace("T", " ")
    else:
        display_time = capture_time
        
    display_img_src = process_and_rotate_image(latest_img_url, cam_rotation)
    
    watermark_html = f"""
    <div style="position: relative; width: 100%; border-radius: 8px; overflow: hidden; border: 1px solid #e6e6e6;">
        <img src="{display_img_src}" style="width: 100%; display: block;">
        <div style="position: absolute; top: 12px; left: 12px; 
                    background-color: rgba(0, 0, 0, 0.65); color: #ffffff; 
                    padding: 8px 12px; border-radius: 6px; 
                    font-family: sans-serif; font-size: 14px; line-height: 1.5;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3); backdrop-filter: blur(2px);">
            <div style="font-weight: bold;">📍 广东连州基地 - 生态位观测点</div>
            <div style="color: #4ade80;">🕒 抓拍时间: {display_time}</div>
        </div>
    </div>
    """
    st.markdown(watermark_html, unsafe_allow_html=True)
    st.caption("🎥 ESP32-CAM 实时流媒体接入 (已启用云端渲染引擎)")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🚰 智能水肥干预")
    
    control_url = f"{SUPABASE_URL}/rest/v1/device_control2?device_name=eq.c3_pump"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    
    try:
        res = requests.get(control_url, headers=headers).json()
        db_record = res[0] if res else {"is_pump_on": False, "is_auto_mode": False}
        current_pump = db_record.get("is_pump_on", False)
        current_auto = db_record.get("is_auto_mode", False)
        
        toggle_auto = st.toggle("🤖 开启无人值守闭环自动灌溉", value=current_auto)
        
        if toggle_auto != current_auto:
            requests.patch(control_url, headers=headers, json={"is_auto_mode": toggle_auto})
            st.rerun()
            
        if toggle_auto:
            st.success("🤖 自动驾驶中：系统正在实时监控 LILYGO 节点指标...")
            current_soil = env_data["soil_moisture"]
            
            if current_soil < 40.0 and not current_pump:
                requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                st.toast("⚠️ 土壤湿度过低，系统已自动下发【开启灌溉】指令！")
                time.sleep(0.5)
                st.rerun()
            elif current_soil >= 70.0 and current_pump:
                requests.patch(control_url, headers=headers, json={"is_pump_on": False})
                st.toast("✅ 土壤湿度已达标，系统已自动下发【关闭灌溉】指令！")
                time.sleep(0.5)
                st.rerun()
                
            if current_pump:
                st.error("🔄 自动化决策：检测到湿度低，正在加压微喷中...")
            else:
                st.info("💤 自动化决策：土壤墒情良好，水泵处于休眠待命状态")
            st.button("🟢 手动启动灌溉 (已由自动模式接管)", disabled=True, use_container_width=True)
            
        else:
            st.warning("👨‍💻 手动遥控中：无人值守系统已暂停")
            if current_pump:
                st.error("🔴 水泵远程运行中...")
                if st.button("🛑 紧急停止灌溉", use_container_width=True):
                    requests.patch(control_url, headers=headers, json={"is_pump_on": False})
                    st.rerun()
            else:
                st.info("🔵 远程管道压力正常，处于待命状态")
                if st.button("🟢 手动远程启动灌溉", use_container_width=True):
                    requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                    st.rerun()
                    
    except Exception as e:
        st.error("连接控制中枢失败，请检查数据库配置")

# ----------------- 右侧：微气候演变趋势区 -----------------
with right_col:
    st.subheader("📈 核心微气候演变趋势 (100周期)")
    
    df_temp = pd.DataFrame(np.random.randn(100, 1) * 0.5 + 30.7, columns=['空气温度 (℃)'])
    df_hum = pd.DataFrame(np.random.randn(100, 1) * 1.5 + 80.1, columns=['空气湿度 (%)'])
    df_light = pd.DataFrame(np.random.randn(100, 1) * 5 + 25.8, columns=['光照强度 (lx)'])
    df_soil = pd.DataFrame(np.random.randn(100, 1) * 0.8 + 72, columns=['土壤含水率 (%)'])
    df_co2 = pd.DataFrame(np.random.randn(100, 1) * 15 + 887, columns=['二氧化碳 (ppm)'])

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
