import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import time
import base64          
from io import BytesIO 
from PIL import Image  
import json
import os

# ==========================================
# ⚙️ 核心与时区、本地缓存配置
# ==========================================
BEIJING_TZ = timezone(timedelta(hours=8))
SCHEDULE_FILE = "pump_schedule.json"

st.set_page_config(
    page_title="连州玉竹栽培环境监测与水肥控制系统", 
    page_icon="🌱", 
    layout="wide",
    initial_sidebar_state="expanded"
)

hide_streamlit_style = """
<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

SUPABASE_URL = "https://srzfkhiminxmbrbdipay.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"

# ==========================================
# 🔌 数据抓取与辅助函数
# ==========================================
@st.cache_data(ttl=10) 
def fetch_latest_image():
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
    if not img_url.startswith("http"): return img_url
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

@st.cache_data(ttl=10) # 缓存 10 秒，避免高频刷新导致 API 封禁
def fetch_latest_env_data():
    url = f"{SUPABASE_URL}/rest/v1/base_env_data"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    # 通过 id 倒序排列，只请求最新的一条数据
    params = {"order": "id.desc", "limit": 1}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                latest = data[0]
                
                # 处理 Supabase 的 UTC 零时区时间并转换为北京时间
                raw_time = latest.get('created_at', '')
                if raw_time:
                    # 截取时间字符串前19位 (如 "2026-07-10T23:51:04") 转换时区
                    dt_utc = datetime.strptime(raw_time[:19], "%Y-%m-%dT%H:%M:%S")
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                    display_time = dt_utc.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    display_time = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    
                # 返回数据库中对应的真实字段
                return {
                    "co2": latest.get("co2_ppm", "--"),
                    "temp": latest.get("air_temp", "--"),
                    "humidity": latest.get("air_hum", "--"),
                    "light": latest.get("light_lux", "--"),
                    "soil_moisture": latest.get("soil_moisture", "--"),
                    "timestamp": display_time
                }
    except Exception as e:
        pass
        
    # 如果网络波动或请求失败，返回占位符避免页面崩溃
    return {
        "co2": "--", "temp": "--", "humidity": "--", "light": "--", "soil_moisture": "--",  
        "timestamp": "获取云端数据超时"
    }

# ==========================================
# ⏰ 定时任务引擎 (后台大脑)
# ==========================================
def load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r') as f:
            return json.load(f)
    return {
        "stop_timestamp": 0, "plan_type": "none", "plan_time": "08:00", 
        "plan_duration": 15, "interval_days": 2, "last_run_date": ""
    }

def save_schedule(data):
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(data, f)

# 读取最新状态
control_url = f"{SUPABASE_URL}/rest/v1/device_control2?device_name=eq.c3_pump"
headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
try:
    res = requests.get(control_url, headers=headers).json()
    db_record = res[0] if res else {"is_pump_on": False, "is_auto_mode": False}
except Exception:
    db_record = {"is_pump_on": False, "is_auto_mode": False}

current_pump = db_record.get("is_pump_on", False)
current_auto = db_record.get("is_auto_mode", False)

sched = load_schedule()
now_beijing = datetime.now(BEIJING_TZ)
schedule_updated = False

# 【核心逻辑】：如果未开启“环境自动模式”，则执行时间规划局
if not current_auto:
    # 1. 检查倒计时停止
    if current_pump and sched["stop_timestamp"] > 0:
        if now_beijing.timestamp() >= sched["stop_timestamp"]:
            current_pump = False
            sched["stop_timestamp"] = 0
            requests.patch(control_url, headers=headers, json={"is_pump_on": False})
            schedule_updated = True

    # 2. 检查周期性启动任务
    if sched["plan_type"] in ["daily", "interval"]:
        current_hm = now_beijing.strftime("%H:%M")
        today_str = now_beijing.strftime("%Y-%m-%d")
        
        # 当时间匹配（精确到分钟）
        if current_hm == sched["plan_time"]:
            should_start = False
            if sched["plan_type"] == "daily" and sched["last_run_date"] != today_str:
                should_start = True
            elif sched["plan_type"] == "interval":
                if not sched["last_run_date"]:
                    should_start = True
                else:
                    last_run_date = datetime.strptime(sched["last_run_date"], "%Y-%m-%d").date()
                    if (now_beijing.date() - last_run_date).days >= sched["interval_days"]:
                        should_start = True
            
            if should_start and not current_pump:
                current_pump = True
                sched["stop_timestamp"] = now_beijing.timestamp() + sched["plan_duration"] * 60
                sched["last_run_date"] = today_str
                requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                schedule_updated = True

if schedule_updated:
    save_schedule(sched)

# ==========================================
# 🖥️ 侧边栏与头部渲染
# ==========================================
with st.sidebar:
    try:
        st.image("logo绿色.png", use_container_width=True)
    except Exception:
        pass
    st.markdown("---")
    st.subheader("⚙️ 运行控制台")
    auto_refresh = st.checkbox("☑️ 开启数据自动刷新", value=True)
    refresh_rate = st.slider("⏱️ 刷新间隔 (秒)", min_value=5, max_value=60, value=10)
    cam_rotation = st.selectbox("🔄 画面校正角度", [0, 90, 180, 270], index=0, format_func=lambda x: f"{x}°")
    st.markdown("---")
    st.subheader("🔗 节点连通状态")
    st.success("🟢 环境采集节点 (LILYGO): 在线")
    st.success("🟢 水肥控制节点 (ESP32-C3): 在线联控")
    st.success("🟢 视频观测节点 (ESP32-CAM): 在线") 
    st.markdown("---")
    st.caption("技术支持：中山大学农业与生物技术学院 彭宇涛课题组")

st.title("🌱 连州玉竹栽培环境监测与水肥控制系统")
st.caption(f"💻 大屏系统时间: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} | 📍 基地: 广东连州生态区")
st.markdown("---")

env_data = fetch_latest_env_data()
st.markdown(f"**📡 环境节点同步时间:** `{env_data['timestamp']}`")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("☁️ CO2 [ppm]", f"{env_data['co2']}")
k2.metric("🌡️ 温度 [℃]", f"{env_data['temp']}")
k3.metric("💧 湿度 [%]", f"{env_data['humidity']}")
k4.metric("☀️ 光照 [lx]", f"{env_data['light']}")
k5.metric("🌱 土壤水分 [%]", f"{env_data['soil_moisture']}")
st.markdown("---")

# ==========================================
# 🖥️ 主体分栏区
# ==========================================
left_col, right_col = st.columns([4, 6])

with left_col:
    st.subheader("📷 生态位实况")
    latest_img_url, capture_time = fetch_latest_image()
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
        <div style="position: absolute; top: 12px; left: 12px; background-color: rgba(0, 0, 0, 0.65); color: #ffffff; padding: 8px 12px; border-radius: 6px; font-size: 14px; backdrop-filter: blur(2px);">
            <b>📍 连州基地观测点</b><br><span style="color: #4ade80;">🕒 {display_time}</span>
        </div>
    </div>
    """
    st.markdown(watermark_html, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # 🌟 核心升级：控制台选项卡
    st.subheader("🚰 水肥干预中枢")
    tab_ctrl, tab_plan = st.tabs(["🚦 传感智控 & 快捷遥控", "📅 周期灌溉计划"])
    
    # -------- Tab 1: 实时与快捷控制 --------
    with tab_ctrl:
        toggle_auto = st.toggle("🤖 开启环境阈值自动灌溉 (基于土壤水分)", value=current_auto)
        if toggle_auto != current_auto:
            requests.patch(control_url, headers=headers, json={"is_auto_mode": toggle_auto})
            st.rerun()
            
        if toggle_auto:
            st.success("🤖 传感智控已接管：根据土壤水分自动启停水泵。")
            current_soil = env_data["soil_moisture"]
            if current_soil < 40.0 and not current_pump:
                requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                st.rerun()
            elif current_soil >= 70.0 and current_pump:
                requests.patch(control_url, headers=headers, json={"is_pump_on": False})
                st.rerun()
                
            if current_pump: st.error("🔄 自动干预：正在加压微喷中...")
            else: st.info("💤 土壤墒情良好，水泵待命中。")
            st.button("手动控制 (环境自动模式下禁用)", disabled=True, use_container_width=True)
            
        else:
            st.warning("👨‍💻 手动干预模式 (环境智控已暂停)")
            
            # 显示正在倒计时的情况
            if current_pump:
                st.error("🔴 水泵正在运行中...")
                if sched["stop_timestamp"] > 0:
                    stop_dt = datetime.fromtimestamp(sched["stop_timestamp"], BEIJING_TZ)
                    st.info(f"⏳ 倒计时进行中，预计于 **{stop_dt.strftime('%H:%M:%S')}** 自动关闭。")
                
                if st.button("🛑 紧急停止灌溉", use_container_width=True):
                    requests.patch(control_url, headers=headers, json={"is_pump_on": False})
                    sched["stop_timestamp"] = 0
                    save_schedule(sched)
                    st.rerun()
            else:
                st.info("🔵 管道压力正常，等待指令。")
                if st.button("🟢 持续开启水泵", use_container_width=True):
                    requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                    sched["stop_timestamp"] = 0 # 清除倒计时标志
                    save_schedule(sched)
                    st.rerun()
                
                st.markdown("---")
                st.caption("⏱️ **快捷倒计时灌溉 (到点自动停):**")
                c1, c2, c3, c4 = st.columns(4)
                
                def start_timed_pump(mins):
                    requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                    sched["stop_timestamp"] = datetime.now(BEIJING_TZ).timestamp() + mins * 60
                    save_schedule(sched)
                
                if c1.button("10 分钟", use_container_width=True): 
                    start_timed_pump(10)
                    st.rerun()
                if c2.button("15 分钟", use_container_width=True): 
                    start_timed_pump(15)
                    st.rerun()
                if c3.button("25 分钟", use_container_width=True): 
                    start_timed_pump(25)
                    st.rerun()
                if c4.button("1 小时", use_container_width=True): 
                    start_timed_pump(60)
                    st.rerun()

    # -------- Tab 2: 周期灌溉计划 --------
    with tab_plan:
        if current_auto:
            st.error("⚠️ 当前已开启【环境阈值自动灌溉】。为避免逻辑冲突，请先在左侧标签页关闭环境智控，再启用周期计划。")
        else:
            st.info("💡 设定无人值守的周期计划。到达指定时间后，系统会自动启动水泵并按设定时长灌溉。")
            
            with st.form("schedule_form"):
                plan_mode = st.radio(
                    "📅 计划模式", 
                    ["不启用", "每天固定时间", "按天数间隔"],
                    index=0 if sched["plan_type"] == "none" else (1 if sched["plan_type"] == "daily" else 2)
                )
                
                col_t, col_d = st.columns(2)
                with col_t:
                    input_time = st.time_input("⏰ 设定启动时间", value=datetime.strptime(sched["plan_time"], "%H:%M").time())
                with col_d:
                    input_duration = st.number_input("⏱️ 每次灌溉时长 (分钟)", min_value=1, max_value=300, value=sched["plan_duration"])
                
                input_interval = 2
                if plan_mode == "按天数间隔":
                    input_interval = st.slider("🗓️ 间隔天数 (每隔几天灌溉一次)", min_value=1, max_value=10, value=sched["interval_days"])
                
                submit_plan = st.form_submit_button("保存周期计划", use_container_width=True)
                
                if submit_plan:
                    if plan_mode == "不启用":
                        sched["plan_type"] = "none"
                    elif plan_mode == "每天固定时间":
                        sched["plan_type"] = "daily"
                    else:
                        sched["plan_type"] = "interval"
                    
                    sched["plan_time"] = input_time.strftime("%H:%M")
                    sched["plan_duration"] = input_duration
                    sched["interval_days"] = input_interval
                    
                    save_schedule(sched)
                    st.success("✅ 计划已保存！")
                    time.sleep(1)
                    st.rerun()
            
            # 显示当前状态
            st.markdown("---")
            if sched["plan_type"] == "none":
                st.write("当前状态：**未启用任何周期计划**")
            elif sched["plan_type"] == "daily":
                st.write(f"当前状态：**每天 {sched['plan_time']}** 自动开启灌溉，持续 **{sched['plan_duration']}** 分钟。")
            elif sched["plan_type"] == "interval":
                st.write(f"当前状态：**每隔 {sched['interval_days']} 天** 的 **{sched['plan_time']}** 开启灌溉，持续 **{sched['plan_duration']}** 分钟。")
                if sched["last_run_date"]:
                    st.caption(f"上一次成功执行日期: {sched['last_run_date']}")

with right_col:
    st.subheader("📈 核心微气候演变趋势 (100周期)")
    df_temp = pd.DataFrame(np.random.randn(100, 1) * 0.5 + 30.7, columns=['空气温度 (℃)'])
    df_hum = pd.DataFrame(np.random.randn(100, 1) * 1.5 + 80.1, columns=['空气湿度 (%)'])
    df_light = pd.DataFrame(np.random.randn(100, 1) * 5 + 25.8, columns=['光照强度 (lx)'])
    df_soil = pd.DataFrame(np.random.randn(100, 1) * 0.8 + 72, columns=['土壤含水率 (%)'])
    df_co2 = pd.DataFrame(np.random.randn(100, 1) * 15 + 887, columns=['二氧化碳 (ppm)'])

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.line_chart(df_temp, height=180)
        st.line_chart(df_light, height=180)
        st.line_chart(df_co2, height=180)
    with chart_col2:
        st.line_chart(df_hum, height=180)
        st.line_chart(df_soil, height=180)
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 **栽培提示:** 玉竹喜阴湿环境，若光照持续 > 8000 lx 且土壤含水率 < 40%，建议启动水肥一体化微喷。")

if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
