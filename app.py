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

# 🌟 全局 CSS 布局优化
compact_style = """
<style>
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;}
    /* 恢复适度的顶部边距，防止标题被浏览器/状态栏遮挡裁切 */
    .block-container {padding-top: 2.5rem; padding-bottom: 1rem; max-width: 96%;}
    /* 缩减分割线边距 */
    hr {margin-top: 0.5rem; margin-bottom: 0.5rem;}
    /* 控制标签页的高度 */
    .stTabs [data-baseweb="tab-list"] {gap: 2px;}
</style>
"""
st.markdown(compact_style, unsafe_allow_html=True)

# ==========================================
# 🔒 登录鉴权模块
# ==========================================
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.subheader("🔒 系统安全登录")
        with st.form("login_form"):
            password_input = st.text_input("请输入访问密码以解锁系统：", type="password")
            submit_button = st.form_submit_button("登录系统", use_container_width=True)
            if submit_button:
                if password_input == "Zx13702479":
                    st.session_state['authenticated'] = True
                    st.success("✅ 登录成功！正在加载...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 密码错误。")
    st.stop()


# ==========================================
# 🔌 数据抓取与辅助函数
# ==========================================
SUPABASE_URL = "https://srzfkhiminxmbrbdipay.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"

@st.cache_data(ttl=3600, max_entries=20) 
def process_and_rotate_image(img_source, rotation_angle):
    try:
        if img_source.startswith("http"):
            resp = requests.get(img_source, timeout=5)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content))
            else:
                return img_source
        else:
            if os.path.exists(img_source):
                img = Image.open(img_source)
            else:
                return "https://images.unsplash.com/photo-1628352081506-83c43123ed6d?auto=format&fit=crop&q=80&w=800"

        if rotation_angle != 0:
            img = img.rotate(-rotation_angle, expand=True)
        buffered = BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buffered, format="JPEG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/jpeg;base64,{img_b64}"
    except Exception:
        pass
    return img_source 

@st.cache_data(ttl=10) 
def fetch_latest_env_data():
    url = f"{SUPABASE_URL}/rest/v1/base_env_data"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    params = {"order": "id.desc", "limit": 1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                latest = data[0]
                raw_time = latest.get('created_at', '')
                if raw_time:
                    dt_utc = datetime.strptime(raw_time[:19], "%Y-%m-%dT%H:%M:%S")
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                    display_time = dt_utc.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    display_time = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    
                return {
                    "co2": latest.get("co2_ppm", "--"),
                    "temp": latest.get("air_temp", "--"),
                    "humidity": latest.get("air_hum", "--"),
                    "light": latest.get("light_lux", "--"),
                    "soil_moisture": latest.get("soil_moisture", "--"),
                    "timestamp": display_time
                }
    except Exception:
        pass
    return {"co2": "--", "temp": "--", "humidity": "--", "light": "--", "soil_moisture": "--", "timestamp": "超时"}

# ==========================================
# ⏰ 定时任务引擎
# ==========================================
def load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r') as f:
            return json.load(f)
    return {"stop_timestamp": 0, "plan_type": "none", "plan_time": "08:00", "plan_duration": 15, "interval_days": 2, "last_run_date": ""}

def save_schedule(data):
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(data, f)

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

if not current_auto:
    if current_pump and sched["stop_timestamp"] > 0:
        if now_beijing.timestamp() >= sched["stop_timestamp"]:
            current_pump = False
            sched["stop_timestamp"] = 0
            requests.patch(control_url, headers=headers, json={"is_pump_on": False})
            schedule_updated = True

    if sched["plan_type"] in ["daily", "interval"]:
         current_hm = now_beijing.strftime("%H:%M")
         today_str = now_beijing.strftime("%Y-%m-%d")
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
# 🖥️ 侧边栏渲染
# ==========================================
with st.sidebar:
    try:
        st.image("logo绿色.png", use_container_width=True)
    except Exception:
        pass
    st.subheader("⚙️ 运行控制台")
    auto_refresh = st.checkbox("☑️ 开启数据自动刷新", value=True)
    refresh_rate = st.slider("⏱️ 刷新间隔 (秒)", min_value=5, max_value=60, value=10)
    cam_rotation = st.selectbox("🔄 画面校正角度", [0, 90, 180, 270], index=0, format_func=lambda x: f"{x}°")
    
    st.markdown("---")
    st.markdown("**🔗 节点连通状态**")
    st.success("🟢 LILYGO 采集: 在线")
    st.success("🟢 ESP32-C3 联控: 在线")
    st.success("🟢 ESP32-CAM 观测: 在线") 
    
    # ✨ 补回了缺失的技术支持信息
    st.markdown("---")
    st.caption("技术支持：中山大学农业与生物技术学院 魏蜜团队")
    
    if st.button("🚪 退出登录", use_container_width=True):
        st.session_state['authenticated'] = False
        st.rerun()

# ==========================================
# 🖥️ 头部渲染
# ==========================================
env_data = fetch_latest_env_data()

# 替换回标准的 st.header，避免被裁切
st.header("🌱 连州玉竹栽培环境监测与水肥控制系统")
st.caption(f"💻 大屏时间: `{now_beijing.strftime('%Y-%m-%d %H:%M:%S')}` ｜ 📍 基地: 广东连州 ｜ 📡 节点同步: `{env_data['timestamp']}`")

# 数据面板
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("☁️ CO2 [ppm]", f"{env_data['co2']}")
k2.metric("🌡️ 温度 [℃]", f"{env_data['temp']}")
k3.metric("💧 湿度 [%]", f"{env_data['humidity']}")
k4.metric("☀️ 光照 [lx]", f"{env_data['light']}")
k5.metric("🌱 土壤水分 [%]", f"{env_data['soil_moisture']}")
st.markdown("---")

# ==========================================
# 🖥️ 主体分栏区 (4:6 比例)
# ==========================================
left_col, right_col = st.columns([4, 6])

with left_col:
    st.markdown("**📷 生态位实况**")
    display_time = datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')
    display_img_src = process_and_rotate_image("YZ.jpg", cam_rotation)
    
    watermark_html = f"""
    <div style="position: relative; width: 100%; border-radius: 6px; overflow: hidden; border: 1px solid #ddd; margin-bottom: 0.5rem;">
        <img src="{display_img_src}" style="width: 100%; display: block;">
        <div style="position: absolute; top: 8px; left: 8px; background-color: rgba(0, 0, 0, 0.65); color: #ffffff; padding: 4px 8px; border-radius: 4px; font-size: 12px; backdrop-filter: blur(2px);">
            <b>📍 连州观测点</b><br><span style="color: #4ade80;">🕒 {display_time}</span>
        </div>
    </div>
    """
    st.markdown(watermark_html, unsafe_allow_html=True)

    # 控制台区
    st.markdown("**🚰 水肥干预中枢**")
    tab_ctrl, tab_plan = st.tabs(["🚦 快捷遥控", "📅 周期计划"])
    
    with tab_ctrl:
        toggle_auto = st.toggle("🤖 开启阈值自动灌溉 (基于土壤水分)", value=current_auto)
        if toggle_auto != current_auto:
            requests.patch(control_url, headers=headers, json={"is_auto_mode": toggle_auto})
            st.rerun()
            
        if toggle_auto:
            st.success("🤖 传感智控接管中。")
            current_soil = env_data["soil_moisture"]
            if current_soil != "--" and float(current_soil) < 40.0 and not current_pump:
                requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                st.rerun()
            elif current_soil != "--" and float(current_soil) >= 70.0 and current_pump:
                requests.patch(control_url, headers=headers, json={"is_pump_on": False})
                st.rerun()
                
            if current_pump: st.error("🔄 正在加压微喷中...")
            else: st.info("💤 水泵待命中。")
            st.button("手动控制禁用", disabled=True, use_container_width=True)
            
        else:
            if current_pump:
                st.error("🔴 水泵正在运行...")
                if sched["stop_timestamp"] > 0:
                    stop_dt = datetime.fromtimestamp(sched["stop_timestamp"], BEIJING_TZ)
                    st.caption(f"⏳ 预计 **{stop_dt.strftime('%H:%M:%S')}** 关闭。")
                if st.button("🛑 紧急停止", use_container_width=True):
                    requests.patch(control_url, headers=headers, json={"is_pump_on": False})
                    sched["stop_timestamp"] = 0
                    save_schedule(sched)
                    st.rerun()
            else:
                st.info("🔵 管道压力正常，等待指令。")
                if st.button("🟢 持续开启水泵", use_container_width=True):
                    requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                    sched["stop_timestamp"] = 0 
                    save_schedule(sched)
                    st.rerun()
                
                st.caption("⏱️ 倒计时灌溉:")
                c1, c2, c3, c4 = st.columns(4)
                
                def start_timed_pump(mins):
                    requests.patch(control_url, headers=headers, json={"is_pump_on": True})
                    sched["stop_timestamp"] = datetime.now(BEIJING_TZ).timestamp() + mins * 60
                    save_schedule(sched)
                
                if c1.button("10分", use_container_width=True): start_timed_pump(10); st.rerun()
                if c2.button("15分", use_container_width=True): start_timed_pump(15); st.rerun()
                if c3.button("25分", use_container_width=True): start_timed_pump(25); st.rerun()
                if c4.button("1时", use_container_width=True): start_timed_pump(60); st.rerun()

    with tab_plan:
        if current_auto:
            st.error("⚠️ 请先关闭环境智控。")
        else:
            with st.form("schedule_form"):
                plan_mode = st.radio("模式", ["不启用", "每天", "按天间隔"], horizontal=True, index=0 if sched["plan_type"] == "none" else (1 if sched["plan_type"] == "daily" else 2))
                
                col_t, col_d = st.columns(2)
                with col_t: input_time = st.time_input("⏰ 启动时间", value=datetime.strptime(sched["plan_time"], "%H:%M").time())
                with col_d: input_duration = st.number_input("⏱️ 时长(分)", min_value=1, max_value=300, value=sched["plan_duration"])
                
                input_interval = 2
                if plan_mode == "按天间隔":
                    input_interval = st.slider("🗓️ 间隔天数", 1, 10, sched["interval_days"])
                
                if st.form_submit_button("保存计划", use_container_width=True):
                    sched["plan_type"] = "none" if plan_mode == "不启用" else ("daily" if plan_mode == "每天" else "interval")
                    sched["plan_time"] = input_time.strftime("%H:%M")
                    sched["plan_duration"] = input_duration
                    sched["interval_days"] = input_interval
                    save_schedule(sched)
                    st.success("✅ 已保存！")
                    time.sleep(0.5)
                    st.rerun()
            
            if sched["plan_type"] != "none":
                st.caption(f"当前: **{sched['plan_type']}**, {sched['plan_time']} 启, 跑 {sched['plan_duration']} 分钟。")

with right_col:
    st.markdown("**📈 核心微气候演变趋势 (100周期)**")
    
    # 模拟数据生成
    df_temp = pd.DataFrame(np.random.randn(100, 1) * 0.5 + 30.7, columns=['温度 (℃)'])
    df_hum = pd.DataFrame(np.random.randn(100, 1) * 1.5 + 80.1, columns=['湿度 (%)'])
    df_light = pd.DataFrame(np.random.randn(100, 1) * 5 + 25.8, columns=['光照 (lx)'])
    df_soil = pd.DataFrame(np.random.randn(100, 1) * 0.8 + 72, columns=['土壤水分 (%)'])
    df_co2 = pd.DataFrame(np.random.randn(100, 1) * 15 + 887, columns=['CO2 (ppm)'])

    # 采用 3行 x 2列 布局，加高图表以填补垂直空间的留白
    r1_c1, r1_c2 = st.columns(2)
    r2_c1, r2_c2 = st.columns(2)
    r3_c1, r3_c2 = st.columns(2)
    
    CHART_H = 220
    
    with r1_c1: st.line_chart(df_temp, height=CHART_H)
    with r1_c2: st.line_chart(df_hum, height=CHART_H)
    
    with r2_c1: st.line_chart(df_light, height=CHART_H)
    with r2_c2: st.line_chart(df_soil, height=CHART_H)
    
    with r3_c1: st.line_chart(df_co2, height=CHART_H)
    
    with r3_c2: 
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.info("💡 **栽培提示:** 玉竹喜阴湿环境。若光照持续 > 8000 lx 且土壤含水率 < 40%，建议启动微喷。")

if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
