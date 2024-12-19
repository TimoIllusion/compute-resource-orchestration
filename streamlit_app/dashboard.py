import streamlit as st
import requests

# Point to the central dashboard
CENTRAL_DASHBOARD_URL = "http://central_dashboard:8000"

st.title("Cluster CPU/Memory Dashboard")

# Fetch node data
try:
    data = requests.get(f"{CENTRAL_DASHBOARD_URL}/api/list_nodes", timeout=5).json()
except Exception as e:
    st.error(f"Failed to fetch node data: {e}")
    st.stop()

for node_id, info in data.items():
    st.subheader(f"Node: {node_id}")
    st.write(f"CPU Usage: {info['cpu_usage']:.2f}%")
    st.write(f"Memory Usage: {info['mem_usage']:.2f} GB")
    current_res = info["reservation"] if info["reservation"] else "None"
    st.write(f"Reserved By: {current_res}")

    # Reservation form
    with st.form(key=f"reserve_form_{node_id}"):
        user = st.text_input("Your name", value="", key=f"user_{node_id}")
        submit = st.form_submit_button("Reserve this node")
        if submit and user.strip():
            try:
                r = requests.post(
                    f"{CENTRAL_DASHBOARD_URL}/api/reserve_node",
                    json={"node_id": node_id, "user_name": user},
                    timeout=5,
                )
                if r.status_code == 200:
                    st.success("Node reserved successfully!")
                    st.rerun()  # Refresh the page to see the updated status
                else:
                    st.error("Failed to reserve node.")
            except Exception as e:
                st.error(f"Error reserving node: {e}")
