import streamlit as st
import sqlite3
import pandas as pd
import os

st.set_page_config(
    page_title="Companion DB Explorer 🔍",
    layout="wide",
    page_icon="🔍"
)

DB_PATH = "full_protopype/under7_companion.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Header
st.markdown("<h1 style='color:#2C3E50;'>🔍 Database Explorer & Editor</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#7F8C8D;'>Inspect sqlite tables, schema columns, explore all row values, and delete database records.</p>", unsafe_allow_html=True)

if not os.path.exists(DB_PATH):
    st.error(f"Database file `{DB_PATH}` not found in the workspace!")
    st.stop()

# Load table names
try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row["name"] for row in cursor.fetchall()]
    conn.close()
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    st.stop()

if not tables:
    st.warning("No tables found in the database.")
    st.stop()

# Sidebar table selection
selected_table = st.sidebar.selectbox("Select Table to Explore:", options=tables)

# Fetch table data and schema info
conn = get_connection()
cursor = conn.cursor()

# Get column names & types
cursor.execute(f"PRAGMA table_info({selected_table})")
schema_info = cursor.fetchall()
columns = [col["name"] for col in schema_info]
pk_col = None
for col in schema_info:
    if col["pk"] == 1:
        pk_col = col["name"]

# If no explicit PK, default to the first column
if not pk_col and columns:
    pk_col = columns[0]

# Retrieve all rows
cursor.execute(f"SELECT * FROM {selected_table}")
rows = cursor.fetchall()
conn.close()

# Dataframe display
data = [dict(row) for row in rows]
df = pd.DataFrame(data, columns=columns)

st.subheader(f"Table: `{selected_table}`")

# Tabs for viewing schema vs content
tab_content, tab_schema = st.tabs(["📊 Row Values", "📐 Table Schema"])

with tab_schema:
    st.markdown("### Columns & Specifications")
    schema_df = pd.DataFrame([
        {
            "CID": col["cid"],
            "Column Name": col["name"],
            "Type": col["type"],
            "Not Null": bool(col["notnull"]),
            "Default Value": col["dflt_value"],
            "Primary Key": bool(col["pk"])
        } for col in schema_info
    ])
    st.dataframe(schema_df, use_container_width=True, hide_index=True)

with tab_content:
    if df.empty:
        st.info(f"The table `{selected_table}` is currently empty.")
    else:
        st.markdown(f"**Total Records:** {len(df)}")
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        
        # Deletion Interface
        st.markdown("### 🗑️ Delete Records")
        
        col_select, col_action = st.columns([2, 1])
        
        with col_select:
            # Let the user select key values to delete
            key_values = df[pk_col].tolist()
            selected_key_to_delete = st.selectbox(
                f"Select {pk_col} value to delete:",
                options=key_values,
                help=f"Identify the row you want to remove using its {pk_col}."
            )
            
        with col_action:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            confirm_delete = st.button(f"Delete Row from {selected_table}", use_container_width=True)
            
        if confirm_delete:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                # Run delete query
                cursor.execute(f"DELETE FROM {selected_table} WHERE {pk_col} = ?", (selected_key_to_delete,))
                conn.commit()
                conn.close()
                st.success(f"Successfully deleted record where {pk_col} = `{selected_key_to_delete}`!")
                time_sleep = st.empty()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to delete record: {e}")
                
        # Danger Zone: Clear entire table
        with st.expander("⚠️ Danger Zone: Clear Table"):
            st.warning(f"This will permanently delete ALL rows in the table `{selected_table}`. This action cannot be undone.")
            clear_confirm = st.text_input(f"Type the table name '{selected_table}' to confirm deletion:", value="")
            clear_btn = st.button("Delete All Rows", type="primary")
            
            if clear_btn:
                if clear_confirm == selected_table:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute(f"DELETE FROM {selected_table}")
                        conn.commit()
                        conn.close()
                        st.success(f"Successfully cleared all rows in table `{selected_table}`!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to clear table: {e}")
                else:
                    st.error("Table name confirmation did not match.")
