import streamlit as st
import pandas as pd
from datetime import datetime

# Helper: safely extract a value from a row
def get_val(row, col):
    try:
        val = row.get(col, "")
        if pd.isna(val):
            return "N/A"
        return val
    except Exception:
        return "N/A"


st.set_page_config(page_title="QC–Audit Workflow", layout="wide")

st.title("QC–Audit Workflow Portal")
st.caption("End-to-end flow for QC, Auditors, and Managers – all in one app.")


# ======================================================
# 0. Session setup
# ======================================================
if "cases_df" not in st.session_state:
    st.session_state["cases_df"] = None  # main database of cases


def get_cases_df():
    return st.session_state["cases_df"]


def set_cases_df(df: pd.DataFrame):
    st.session_state["cases_df"] = df

def week_filter_ui(df: pd.DataFrame):
    """Returns (selected_week, filtered_df)."""
    if df is None or "week" not in df.columns:
        return "All", df

    weeks = df["week"].dropna().unique().tolist()
    # Sort safely (numbers or strings)
    try:
        weeks = sorted(weeks)
    except Exception:
        weeks = sorted([str(w) for w in weeks])

    selected_week = st.selectbox("Week", ["All"] + weeks, key="week_selector")

    if selected_week == "All":
        return selected_week, df
    return selected_week, df[df["week"] == selected_week]


# ======================================================
# 1. Helper: Initialize DB from QC Excel
#    (maps from your real columns + adds workflow columns)
# ======================================================
def init_db_from_qc_file(uploaded_file) -> pd.DataFrame:
    # Detect type
    fname = uploaded_file.name.lower()
    if fname.endswith(".csv"):
        base_df = pd.read_csv(uploaded_file)
    else:
        base_df = pd.read_excel(uploaded_file)

    # Make sure essential columns exist (from your file structure)
    required_cols = [
        "auditor",
        "addressid",
        "week",
        "program",
        "trackingid",
        "pdp",
        "pre",
        "auditordpgranularity",
        "auditorregranularity",
        "auditordp_",
        "auditorre_",
        "auditorremarks",
        "auditoractiontaken",
        "disagreement",
        "qc2_dp",
        "qc2_re",
        "auditorcomment",
    ]
    missing = [c for c in required_cols if c not in base_df.columns]
    if missing:
        st.warning(f"These expected columns were not found in the upload: {missing}")

    df = base_df.copy()

    # Add workflow columns
    if "assigned_to" not in df.columns:
        df["assigned_to"] = ""  # which auditor is responsible (string)

    if "auditor_decision" not in df.columns:
        df["auditor_decision"] = ""  # Agree / Appeal

    if "auditor_note" not in df.columns:
        df["auditor_note"] = ""  # auditor's internal note

    if "appeal_text" not in df.columns:
        df["appeal_text"] = ""  # text explaining appeal

    if "qc_final_judgment" not in df.columns:
        df["qc_final_judgment"] = ""  # Accept Appeal / Reject Appeal

    if "qc_note" not in df.columns:
        df["qc_note"] = ""  # QC note on final decision

    # NEW: who gave the final judgment
    if "qc_name" not in df.columns:
        df["qc_name"] = ""  # QC reviewer name / ID

    if "status" not in df.columns:
        # Unassigned / Assigned / Reviewed / Appealed / Completed
        df["status"] = "Unassigned"


    return df


# ======================================================
# 2. Sidebar: role & user selection
# ======================================================
with st.sidebar:
    st.header("User & Role")

    role = st.selectbox(
        "Select your role",
        ["QC", "Auditor", "Manager"],
    )

    # Name is mainly used for Auditor; QC/Manager can leave generic
    current_user = st.text_input(
        "Your name / ID (for filtering data)",
        placeholder="e.g., prashanth",
    )

    st.markdown("---")
    st.markdown("### Data export")
    if get_cases_df() is not None:
        csv_bytes = get_cases_df().to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download current cases CSV",
            data=csv_bytes,
            file_name="cases_export.csv",
            mime="text/csv",
        )


# ======================================================
# 3. Main content per role
# ======================================================

cases_df = get_cases_df()

# ------------- ROLE: QC -------------
if role == "QC":
    st.subheader("QC Dashboard")

    # If DB is empty, show upload to initialize
    if cases_df is None:
        st.info("No case database yet. Upload a QC Excel/CSV file to initialize.")

        upload = st.file_uploader(
            "Upload initial QC cases file",
            type=["xlsx", "xls", "csv"],
        )
        if upload is not None:
            if st.button("Initialize cases database from this file"):
                df = init_db_from_qc_file(upload)
                set_cases_df(df)
                st.success("Cases database initialized. Go to 'Assign Cases' tab.")
    else:
        # QC view with tabs
        tab_assign, tab_appeals, tab_qc_tracker, tab_weekly = st.tabs(
            ["Assign Cases", "Review Appeals", "My Judgments", "📅 Weekly Dashboard"]
            )



        # ---------- TAB: Assign Cases ----------
        with tab_assign:
            st.markdown("### Assign cases to auditors")

            unassigned = cases_df[cases_df["status"] == "Unassigned"].copy()
            st.write(f"Unassigned cases: {len(unassigned)}")

            if unassigned.empty:
                st.info("No unassigned cases. You can update assignments in the data table if needed.")
            else:
                st.dataframe(
                    unassigned[["addressid", "auditor", "program", "week"]],
                    use_container_width=True,
                )

                # Pick an auditor to assign to
                # You can either pick from existing auditors or type a new name
                existing_auditors = sorted(cases_df["auditor"].dropna().astype(str).unique())
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    assign_mode = st.radio(
                        "Assign to",
                        ["Existing 'auditor' column", "Custom name"],
                        horizontal=False,
                    )

                if assign_mode == "Existing 'auditor' column":
                    # Use the same 'auditor' as assigned_to
                    st.caption("Assigning each case to the same name from its 'auditor' column.")
                    if st.button("Batch assign all unassigned cases to their auditor and mark as 'Assigned'"):
                        cases_df.loc[cases_df["status"] == "Unassigned", "assigned_to"] = \
                            cases_df.loc[cases_df["status"] == "Unassigned", "auditor"]
                        cases_df.loc[cases_df["status"] == "Unassigned", "status"] = "Assigned"
                        set_cases_df(cases_df)
                        st.success("All unassigned cases assigned to their auditors.")
                else:
                    with col_a2:
                        target_auditor = st.text_input("Enter auditor name for assignment", value="")
                    case_ids_to_assign = st.multiselect(
                        "Select addressid(s) to assign",
                        unassigned["addressid"].astype(str).tolist(),
                    )
                    if st.button("Assign selected cases to this auditor"):
                        if not target_auditor.strip():
                            st.warning("Please enter a valid auditor name.")
                        elif not case_ids_to_assign:
                            st.warning("Select at least one case to assign.")
                        else:
                            mask = cases_df["addressid"].astype(str).isin(case_ids_to_assign)
                            cases_df.loc[mask, "assigned_to"] = target_auditor.strip()
                            cases_df.loc[mask, "status"] = "Assigned"
                            set_cases_df(cases_df)
                            st.success(f"Assigned {len(case_ids_to_assign)} case(s) to {target_auditor}.")

        # ---------- TAB: Review Appeals ----------
        with tab_appeals:
            st.markdown("### Review appealed cases")

            if cases_df is None:
                st.info("No data loaded.")
            else:
                appealed = cases_df[cases_df["status"] == "Appealed"].copy()
                st.write(f"Appealed cases: {len(appealed)}")

                if appealed.empty:
                    st.info("No appealed cases pending QC review.")
                else:
                    st.dataframe(
                        appealed[["addressid", "assigned_to", "auditor_decision", "appeal_text"]],
                        use_container_width=True,
                    )

                    selected_id = st.selectbox(
                        "Select an appealed case (addressid)",
                        appealed["addressid"].astype(str).tolist(),
                    )

                    row = appealed[appealed["addressid"].astype(str) == selected_id].iloc[0]

                    st.markdown("#### Case details")
                    c1, c2 = st.columns(2)
                    c1.write(f"**addressid:** {row['addressid']}")
                    c1.write(f"**assigned_to (auditor):** {row['assigned_to']}")
                    c1.write(f"**program:** {row.get('program', '')}")
                    c2.write(f"**week:** {row.get('week', '')}")
                    c2.write(f"**disagreement:** {row.get('disagreement', '')}")
                    c2.write(f"**auditor decision:** {row.get('auditor_decision', '')}")

                    st.markdown("**Auditor appeal text:**")
                    st.write(row.get("appeal_text", ""))

                    st.markdown("**Auditor note:**")
                    st.write(row.get("auditor_note", ""))

                    st.markdown("---")
                    st.markdown("#### QC final judgment")

                    qc_choice = st.radio(
                        "Final judgment",
                        ["Accept Appeal", "Reject Appeal"], 
                        horizontal=True,
                        key="qc_final_choice",
                    )

                    qc_note = st.text_area(
                        "QC note (optional)",
                        key="qc_final_note",
                    )

                    if st.button("Save QC final judgment"):
                        mask = cases_df["addressid"].astype(str) == selected_id
                        cases_df.loc[mask, "qc_final_judgment"] = qc_choice
                        cases_df.loc[mask, "qc_note"] = qc_note
                        cases_df.loc[mask, "status"] = "Completed"

    # NEW: track which QC user took this decision
                        if current_user.strip():
                            cases_df.loc[mask, "qc_name"] = current_user.strip()

                        set_cases_df(cases_df)
                        st.success(f"Final judgment saved for addressid {selected_id}.")

                # ---------- TAB: QC Tracker ----------
        with tab_qc_tracker:
            st.markdown("### My final judgments / tracker")

            df_tracker = cases_df[cases_df["qc_final_judgment"] != ""].copy()

            # If QC typed their name in sidebar, filter to only their cases
            if current_user.strip():
                df_tracker = df_tracker[df_tracker["qc_name"] == current_user.strip()]

            st.write(f"Total cases with final judgment: {len(df_tracker)}")

            if df_tracker.empty:
                st.info("No cases with final judgment yet for this QC.")
            else:
                # Some quick stats
                accepted = (df_tracker["qc_final_judgment"] == "Accept Appeal").sum()
                rejected = (df_tracker["qc_final_judgment"] == "Reject Appeal").sum()

                c1, c2, c3 = st.columns(3)
                c1.metric("Accepted appeals", accepted)
                c2.metric("Rejected appeals", rejected)
                c3.metric("Completed (total)", len(df_tracker))

                st.markdown("#### Cases list")
                st.dataframe(
                    df_tracker[
                        [
                            "addressid",
                            "assigned_to",
                            "auditor_decision",
                            "qc_final_judgment",
                            "status",
                            "disagreement",
                            "program",
                            "week",
                            "qc_note",
                        ]
                    ],
                    use_container_width=True,
                )
        with tab_weekly:
            st.subheader("📅 Weekly Dashboard")

            selected_week, dfw = week_filter_ui(cases_df)

            if dfw is None:
                st.info("No data loaded yet.")
            else:
                # KPIs
                total = len(dfw)
                unassigned = (dfw["status"] == "Unassigned").sum()
                assigned = (dfw["status"] == "Assigned").sum()
                reviewed = (dfw["status"] == "Reviewed").sum()
                appealed = (dfw["status"] == "Appealed").sum()
                completed = (dfw["status"] == "Completed").sum()

                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric("Total", total)
                c2.metric("Unassigned", unassigned)
                c3.metric("Assigned", assigned)
                c4.metric("Reviewed", reviewed)
                c5.metric("Appealed", appealed)
                c6.metric("Completed", completed)

                # Quality KPIs (only meaningful if qc_final_judgment is used)
                accepted = 0
                rejected = 0
                if "qc_final_judgment" in dfw.columns:
                    accepted = (dfw["qc_final_judgment"] == "Accept Appeal").sum()
                    rejected = (dfw["qc_final_judgment"] == "Reject Appeal").sum()

                st.markdown("### Quality KPIs")
                k1, k2, k3 = st.columns(3)
                appeal_rate = (appealed / total * 100) if total else 0
                completion_rate = (completed / total * 100) if total else 0
                accept_rate = (accepted / (accepted + rejected) * 100) if (accepted + rejected) else 0
                k1.metric("Appeal Rate", f"{appeal_rate:.1f}%")
                k2.metric("Completion Rate", f"{completion_rate:.1f}%")
                k3.metric("Appeal Accept Rate", f"{accept_rate:.1f}%")

                st.markdown("---")

                # Week-wise summary table (for All only, or still ok for single week)
                st.markdown("### Week-wise Summary")
                if "week" in cases_df.columns:
                    wk = cases_df.groupby("week").agg(
                        total_cases=("addressid", "count"),
                        appealed=("status", lambda x: (x == "Appealed").sum()),
                        completed=("status", lambda x: (x == "Completed").sum()),
                    ).reset_index()

                    wk["appeal_rate_%"] = (wk["appealed"] / wk["total_cases"] * 100).round(1)
                    wk["completion_rate_%"] = (wk["completed"] / wk["total_cases"] * 100).round(1)

                    st.dataframe(wk, use_container_width=True)

                st.markdown("---")

                # Disagreement breakdown
                st.markdown("### Disagreement Breakdown")
                if "disagreement" in dfw.columns:
                    dis = dfw.groupby("disagreement")["addressid"].count().reset_index()
                    dis.columns = ["disagreement", "case_count"]
                    st.dataframe(dis, use_container_width=True)

                st.markdown("---")
                st.markdown("### Cases (filtered)")
                show_cols = [c for c in ["addressid", "assigned_to", "status", "disagreement", "program", "week"] if c in dfw.columns]
                st.dataframe(dfw[show_cols], use_container_width=True)



# ------------- ROLE: Auditor -------------
# ------------- ROLE: Auditor -------------
elif role == "Auditor":
    st.subheader("Auditor Dashboard")

    if cases_df is None:
        st.info("No cases database available. Ask QC to initialize it first.")
    else:
        # Identify current auditor name:
        all_assigned = cases_df[cases_df["assigned_to"] != ""]
        auditors_list = sorted(all_assigned["assigned_to"].dropna().astype(str).unique())

        if not auditors_list:
            st.info("No cases have been assigned yet.")
        else:
            if current_user.strip() and current_user.strip() in auditors_list:
                auditor_name = current_user.strip()
            else:
                auditor_name = st.selectbox(
                    "Select your auditor name",
                    auditors_list,
                )

            my_cases = cases_df[cases_df["assigned_to"] == auditor_name].copy()

            st.write(f"Cases assigned to **{auditor_name}**: {len(my_cases)}")

            if my_cases.empty:
                st.info("You have no assigned cases.")
            else:
                # Metrics
                pending = my_cases[my_cases["status"].isin(["Assigned", "Reviewed"])].shape[0]
                appealed = my_cases[my_cases["status"] == "Appealed"].shape[0]
                completed = my_cases[my_cases["status"] == "Completed"].shape[0]

                c1, c2, c3 = st.columns(3)
                c1.metric("Pending (work not finished)", pending)
                c2.metric("Appealed (waiting QC)", appealed)
                c3.metric("Completed", completed)

                st.markdown("---")

                # List of cases
                st.markdown("### Your cases")
                st.dataframe(
                    my_cases[["addressid", "status", "disagreement", "program", "week"]],
                    use_container_width=True,
                )

                st.markdown("### Case review")

                selectable_ids = my_cases["addressid"].astype(str).tolist()
                selected_id = st.selectbox(
                    "Select a case (addressid)",
                    selectable_ids,
                )

                row = my_cases[my_cases["addressid"].astype(str) == selected_id].iloc[0]
               

                # ---------- 4-minute timer for this auditor + case ----------
                # Timer key is unique per auditor + case
                timer_key = f"start_time_{auditor_name}_{selected_id}"
                submitted_key = f"submitted_{auditor_name}_{selected_id}"


                # Start timer only if not already submitted
                if submitted_key not in st.session_state:
                    if timer_key not in st.session_state:
                        st.session_state[timer_key] = datetime.now().isoformat()

                    start_time = datetime.fromisoformat(st.session_state[timer_key])
                    elapsed_secs = (datetime.now() - start_time).total_seconds()

                    TOTAL_ALLOWED = 4 * 60
                    remaining_secs = int(TOTAL_ALLOWED - elapsed_secs)
                    time_over = remaining_secs <= 0

                    st.markdown("#### ⏱️ Appeal time window")
                    if time_over:
                        st.error("Time over: more than 4 minutes have passed for this case in this session.")
                    else:
                        mins, secs = divmod(remaining_secs, 60)
                        st.metric("Time left to submit decision", f"{mins:02d}:{secs:02d}")
                else:
                    # Already submitted – freeze timer display
                    st.markdown("#### ⏱️ Appeal time window")
                    st.success("Decision submitted — timer stopped.")
                    time_over = True  # lock editing


                

                # ========== FULL CASE DETAILS ==========

                st.markdown("#### Overall status & IDs")
                b1, b2, b3 = st.columns(3)
                b1.write(f"**addressid:** {get_val(row, 'addressid')}")
                b1.write(f"**program:** {get_val(row, 'program')}")
                b1.write(f"**week:** {get_val(row, 'week')}")
                b2.write(f"**countrycode:** {get_val(row, 'countrycode')}")
                b2.write(f"**region:** {get_val(row, 'region')}")
                b2.write(f"**usecase:** {get_val(row, 'usecase')}")
                b3.write(f"**trackingid:** {get_val(row, 'trackingid')}")
                b3.write(f"**status:** {get_val(row, 'status')}")
                b3.write(f"**disagreement:** {get_val(row, 'disagreement')}")

                st.markdown("---")

                # ----- DP block -----
                with st.expander("🟦 Delivery Point (DP)", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**PDP (before audit):**")
                        st.code(str(get_val(row, "pdp")))
                        st.write("**DP geocodes (after audit – auditordp_):**")
                        st.code(str(get_val(row, "auditordp_")))
                    with c2:
                        st.write("**Auditor DP granularity (auditordpgranularity):**")
                        st.write(str(get_val(row, "auditordpgranularity")))
                        st.write("**QC DP granularity (dp_granularity):**")
                        st.write(str(get_val(row, "dp_granularity")))
                        st.write("**QC2 DP bucket (qc2_dp):**")
                        st.write(str(get_val(row, "qc2_dp")))

                    st.markdown("**Reason DP issue (reasondpissue):**")
                    st.write(str(get_val(row, "reasondpissue")))

                # ----- RE block -----
                with st.expander("🟩 Road Entry (RE)", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**PRE (before audit):**")
                        st.code(str(get_val(row, "pre")))
                        st.write("**RE geocodes (after audit – auditorre_):**")
                        st.code(str(get_val(row, "auditorre_")))
                    with c2:
                        st.write("**Auditor RE granularity (auditorregranularity):**")
                        st.write(str(get_val(row, "auditorregranularity")))
                        st.write("**QC RE granularity (re_granularity):**")
                        st.write(str(get_val(row, "re_granularity")))
                        st.write("**QC2 RE bucket (qc2_re):**")
                        st.write(str(get_val(row, "qc2_re")))

                    st.markdown("**Reason RE issue (reasonreissue):**")
                    st.write(str(get_val(row, "reasonreissue")))

                # ----- Geofence / tolerance block -----
                with st.expander("🟨 Geofence & Tolerance", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**Auditor pre-tolerance:**")
                        st.write(str(get_val(row, "auditor_pre_tolerance")))
                        st.write("**Auditor post-tolerance:**")
                        st.write(str(get_val(row, "auditor_post_tolerance")))
                        st.write("**Should be unlocatable:**")
                        st.write(str(get_val(row, "shouldbeunlocatable")))
                    with c2:
                        st.write("**QC2 tolerance (qc2_tolerance):**")
                        st.write(str(get_val(row, "qc2_tolerance")))
                        st.write("**Reason geofence issue (reasongeofenceissue):**")
                        st.write(str(get_val(row, "reasongeofenceissue")))
                        st.write("**Reason bucket error (reasonbucketerror):**")
                        st.write(str(get_val(row, "reasonbucketerror")))

                # ----- Judgement / comments / sources -----
                with st.expander("📝 Comments, Judgments & Sources", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**Auditor remarks (auditorremarks):**")
                        st.write(str(get_val(row, "auditorremarks")))
                        st.write("**Auditor action taken (auditoractiontaken):**")
                        st.write(str(get_val(row, "auditoractiontaken")))
                        st.write("**QC2 judgment (qc2_judgement):**")
                        st.write(str(get_val(row, "qc2_judgement")))
                        st.write("**QC2 confidence (qc2confidence):**")
                        st.write(str(get_val(row, "qc2confidence")))
                    with c2:
                        st.write("**QC comment on auditor (auditorcomment):**")
                        st.write(str(get_val(row, "auditorcomment")))
                        st.write("**GeoCode source (geocodesource):**")
                        st.write(str(get_val(row, "geocodesource")))
                        st.write("**QC2 source (qc2source):**")
                        st.write(str(get_val(row, "qc2source")))
                        st.write("**QC2 date (qc2_date):**")
                        st.write(str(get_val(row, "qc2_date")))
                        st.write("**QC2 GAM issue (qc2_gam_issue):**")
                        st.write(str(get_val(row, "qc2_gam_issue")))

                st.markdown("---")
                st.markdown("#### Your decision")

                current_status = row.get("status", "Assigned")

                # Read-only info if already appealed or completed
                if current_status == "Appealed":
                    st.info("This case is already appealed and waiting for QC. You cannot modify it.")
                    st.markdown("**Your previous decision:**")
                    st.write(f"Decision: {row.get('auditor_decision', '')}")
                    st.write(f"Note: {row.get('auditor_note', '')}")
                    st.write("**Appeal text:**")
                    st.write(row.get("appeal_text", ""))
                elif current_status == "Completed":
                    st.success("QC has completed this case. Below are the final results:")

                    st.markdown("### 🏁 Final QC Decision")
                    st.write(f"**QC Final Judgment:** {row.get('qc_final_judgment', 'N/A')}")

                    st.markdown("### 📝 QC Final Notes")
                    st.write(row.get("qc_note", 'No comments provided.'))

                    st.markdown("### 🔁 Your submission")
                    st.write(f"**Your Decision:** {row.get('auditor_decision', '')}")
                    st.write(f"**Your Note:** {row.get('auditor_note', '')}")
                    st.write("**Appeal text:**")
                    st.write(row.get("appeal_text", "No appeal text."))
                else:
                    # ---------- Editable decision section (ONE textbox only) ----------
                    case_key = f"{auditor_name}_{selected_id}"

                    decision = st.radio(
                        "Choose your action for this case",
                        ["Agree with QC", "Appeal"],
                        horizontal=True,
                        key=f"aud_decision_{case_key}",
                    )

                    # SINGLE textbox only
                    if decision == "Appeal":
                        message_to_qc = st.text_area(
                            "Appeal message to send to QC (required)",
                            value=str(row.get("appeal_text", "")),
                            key=f"appeal_text_{case_key}",
                            height=140,
                        )
                    else:
                        message_to_qc = st.text_area(
                            "Comment (optional)",
                            value=str(row.get("auditor_note", "")),
                            key=f"agree_comment_{case_key}",
                            height=100,
                        )

                    if st.button("Save my decision for this case", key=f"save_{case_key}"):

                        if decision == "Appeal" and not message_to_qc.strip():
                            st.error("Please enter your appeal message before submitting.")
                            st.stop()

                        mask = cases_df["addressid"].astype(str) == selected_id

                        if decision == "Agree with QC":
                            cases_df.loc[mask, "auditor_decision"] = "Agree"
                            cases_df.loc[mask, "auditor_note"] = message_to_qc
                            cases_df.loc[mask, "appeal_text"] = ""
                            cases_df.loc[mask, "status"] = "Completed"
                            cases_df.loc[mask, "qc_final_judgment"] = "Auditor agreed with QC"
                            cases_df.loc[mask, "qc_note"] = ""
                        else:
                            cases_df.loc[mask, "auditor_decision"] = "Appeal"
                            cases_df.loc[mask, "appeal_text"] = message_to_qc
                            cases_df.loc[mask, "auditor_note"] = ""
                            cases_df.loc[mask, "status"] = "Appealed"

                        # 🔒 stop timer after submit
                        submitted_key = f"submitted_{auditor_name}_{selected_id}"
                        st.session_state[submitted_key] = True

                        set_cases_df(cases_df)
                        st.success(f"Decision saved for addressid {selected_id}.")





# ------------- ROLE: Manager -------------
elif role == "Manager":
    st.subheader("Manager Dashboard")

    if cases_df is None:
        st.info("No cases database available. Ask QC to initialize it first.")
    else:
        total = len(cases_df)
        unassigned = (cases_df["status"] == "Unassigned").sum()
        assigned = (cases_df["status"] == "Assigned").sum()
        reviewed = (cases_df["status"] == "Reviewed").sum()
        appealed = (cases_df["status"] == "Appealed").sum()
        completed = (cases_df["status"] == "Completed").sum()

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total cases", total)
        c2.metric("Unassigned", unassigned)
        c3.metric("Assigned", assigned)
        c4.metric("Reviewed", reviewed)
        c5.metric("Appealed", appealed)
        c6.metric("Completed", completed)

        st.markdown("---")
        st.markdown("### Cases by Auditor")

        if "assigned_to" in cases_df.columns:
            by_auditor = cases_df.groupby("assigned_to")["addressid"].count().reset_index()
            by_auditor.columns = ["assigned_to", "case_count"]
            st.dataframe(by_auditor, use_container_width=True)
        else:
            st.info("No 'assigned_to' column yet; QC must assign cases first.")

        st.markdown("### Cases by Disagreement type")
        if "disagreement" in cases_df.columns:
            by_dis = cases_df.groupby("disagreement")["addressid"].count().reset_index()
            by_dis.columns = ["disagreement", "case_count"]
            st.dataframe(by_dis, use_container_width=True)

        st.markdown("### Raw data preview")
        st.dataframe(cases_df.head(50), use_container_width=True)
    st.markdown("---")
    st.subheader("📅 Weekly Dashboard")

    selected_week, dfw = week_filter_ui(cases_df)

    total = len(dfw)
    appealed = (dfw["status"] == "Appealed").sum()
    completed = (dfw["status"] == "Completed").sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total cases", total)
    c2.metric("Appealed", appealed)
    c3.metric("Completed", completed)

    st.dataframe(dfw[["addressid","assigned_to","status","disagreement","program","week"]], use_container_width=True)

