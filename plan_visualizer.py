"""
This file contains functions to generate Gantt charts of schedules and time series plots in tabs 4 and 5.
"""
from production_system import ProductionSystem
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objs as go
import plotly.io as pio
from datetime import datetime, timezone
import tzlocal

class SchedulePlotter:
    @staticmethod
    def make_gantt_chart(production_system, title="Schedule Gantt Chart"):
        """
        Returns HTML for a Plotly Gantt chart showing Workstation and Worker status histories.
        """
        #print(f"plan_visualizer.py: plotting {title}...")

        local_tz = tzlocal.get_localzone()
        fig = go.Figure()

        # --- Workstation Gantt ---
        ws_y_labels = []
        ws_y = 0
        workstation_status_colors = {
            "EMPTY": "#e0e0e0",
            "IDLE": "#b0c4de",
            "WAITING_FOR_MATERIAL": "#ffd966",
            "WAITING_FOR_WORKER": "#f4cccc",
            "WAITING_FOR_TOOLS": "#f6b26b",
            "SETUP": "#6fa8dc",
            "BUSY": "#93c47d",
            "BLOCKED": "#e06666",
            "MAINTENANCE": "#a4c2f4",
            "ERROR": "#cc0000",
            "REPAIR": "#674ea7"
        }
        for ws in production_system.workstations.values():
            ws_y_labels.append(f"Workstation: {ws.workstation_id}")
            history = ws.status_history
            for idx in range(len(history) - 1):
                t_start, stati = history[idx]
                t_end, _ = history[idx + 1]
                if t_end <= t_start:
                    continue
                left = datetime.fromtimestamp(t_start, tz=local_tz)
                right = datetime.fromtimestamp(t_end, tz=local_tz)
                s = ", ".join(stati) if stati else "UNKNOWN"
                color = workstation_status_colors.get(s, "#cccccc")
                # Gray outline
                # fig.add_trace(go.Scatter(
                #     x=[left, right],
                #     y=[ws_y, ws_y],
                #     mode='lines',
                #     line=dict(color='gray', width=18),  # slightly wider than main bar
                #     hoverinfo='skip',
                #     showlegend=False
                # ))
                # Draw a horizontal line for the interval
                fig.add_trace(go.Scatter(
                    x=[left, right],
                    y=[ws_y, ws_y],
                    mode='lines',
                    line=dict(color=color, width=16, dash='solid'),  # main bar
                    marker=dict(line=dict(color='gray', width=1)),   # outline (for markers, not lines)
                    hovertemplate=f"Workstation: {ws.workstation_id}<br>Status: {s}<br>Start: {left.strftime('%d.%m.%Y %H:%M')}<br>End: {right.strftime('%d.%m.%Y %H:%M')}<extra></extra>",
                    showlegend=False
                ))
            ws_y += 1

        # --- Worker Gantt ---
        wrk_y_labels = []
        wrk_y = ws_y  # Continue y-axis after workstations
        worker_status_colors = {
            "IDLE": "#b0c4de",
            "WALKING": "#ffe599",
            "SETTING_UP": "#6fa8dc",
            "BUSY": "#93c47d"
        }
        for worker in production_system.workers.values():
            wrk_y_labels.append(f"Worker: {worker.worker_id}")
            history = worker.status_history
            for idx in range(len(history) - 1):
                t_start, s = history[idx]
                t_end, _ = history[idx + 1]
                if t_end <= t_start:
                    continue
                left = datetime.fromtimestamp(t_start, tz=local_tz)
                right = datetime.fromtimestamp(t_end, tz=local_tz)
                color = worker_status_colors.get(s, "#cccccc")
                # Gray outline
                # fig.add_trace(go.Scatter(
                #     x=[left, right],
                #     y=[wrk_y, wrk_y],
                #     mode='lines',
                #     line=dict(color='gray', width=18),  # slightly wider than main bar
                #     hoverinfo='skip',
                #     showlegend=False
                # ))
                fig.add_trace(go.Scatter(
                    x=[left, right],
                    y=[wrk_y, wrk_y],
                    mode='lines',
                    line=dict(color=color, width=16),
                    hovertemplate=f"Worker: {worker.worker_id}<br>Status: {s}<br>Start: {left.strftime('%d.%m.%Y %H:%M')}<br>End: {right.strftime('%d.%m.%Y %H:%M')}<extra></extra>",
                    showlegend=False
                ))
            wrk_y += 1

        # --- Y-axis labels ---
        y_labels = ws_y_labels + wrk_y_labels
        fig.update_yaxes(
            tickvals=list(range(len(y_labels))),
            ticktext=y_labels,
            autorange="reversed",
            range=[-0.5, len(y_labels) - 0.5]  # Ensures all lanes are shown, even if empty
        )

        # --- X-axis formatting ---
        fig.update_xaxes(
            title="Time",
            type="date"
        )

        fig.update_layout(
            title=title,
            bargap=0.2,
            height=24 * (len(y_labels) + 2),
            margin=dict(l=120, r=20, t=60, b=40),
            template="plotly_white",
            hovermode="closest",
            yaxis_title="",
        )

        #print(pio.to_html(fig, full_html=False, include_plotlyjs='cdn'))

        # Figure abspeichern
        #with open("gantt_chart.html", "w", encoding="utf-8") as f:
        #    f.write(pio.to_html(fig, full_html=False, include_plotlyjs='cdn'))

        return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')  # full_html=False, include_plotlyjs='cdn'

'''
class SchedulePlotter:

    @staticmethod
    def make_gantt_chart(production_system : ProductionSystem, fig=None):
        
        # Returns a PyPlot figure with a Gantt chart showing Workstation and Worker status histories.
        # To be inserted in a widget in ManualPlanningDialog.
        
        # --- Helper: Status color mapping ---
        # You may want to adjust these colors for your statuses
        workstation_status_colors = {
            "EMPTY": "#e0e0e0",
            "IDLE": "#b0c4de",
            "WAITING_FOR_MATERIAL": "#ffd966",
            "WAITING_FOR_WORKER": "#f4cccc",
            "WAITING_FOR_TOOLS": "#f6b26b",
            "SETUP": "#6fa8dc",
            "BUSY": "#93c47d",
            "BLOCKED": "#e06666",
            "MAINTENANCE": "#a4c2f4",
            "ERROR": "#cc0000",
            "REPAIR": "#674ea7"
        }
        worker_status_colors = {
            "IDLE": "#b0c4de",
            "WALKING": "#ffe599",
            "SETTING_UP": "#6fa8dc",
            "BUSY": "#93c47d"
        }

        # --- Prepare figure and axes ---
        # Use provided figure or create a new one
        if fig is None:
            fig, (ax_ws, ax_wrk) = plt.subplots(2, 1, figsize=(16, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        else:
            fig.clear()
            ax_ws, ax_wrk = fig.subplots(2, 1, sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        #fig, (ax_ws, ax_wrk) = plt.subplots(2, 1, figsize=(16, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        fig.subplots_adjust(hspace=0.2)
        ax_ws.set_title("Workstation schedule")
        ax_wrk.set_title("Worker schedule")

        # --- Workstation Gantt ---
        ws_labels = []
        ws_y = 0
        for ws in production_system.workstations.values():
            ws_labels.append(ws.workstation_id)
            history = ws.status_history
            for idx in range(len(history) - 1):
                t_start, stati = history[idx]
                t_end, _ = history[idx + 1]
                if t_end <= t_start:
                    continue  # skip 0-duration or negative
                left = mdates.date2num(datetime.fromtimestamp(t_start, tz=timezone.utc))  # tz=timezone.utc
                width = (t_end - t_start) / 86400  # seconds to days
                # stati is a list of status names (see log_status_change)
                for s in stati:
                    color = workstation_status_colors.get(s, "#cccccc")
                    ax_ws.barh(ws_y, width, left=left, color=color, edgecolor='black', height=0.8)
                    # Optionally, add text label
                    ax_ws.text(left + width / 2, ws_y, s, va='center', ha='center', fontsize=6, color='black')
            ws_y += 1
        ax_ws.set_yticks(range(len(ws_labels)))
        ax_ws.set_yticklabels(ws_labels)
        ax_ws.invert_yaxis()
        ax_ws.grid(axis='x', linestyle=':', alpha=0.5)

        # --- Worker Gantt ---
        wrk_labels = []
        wrk_y = 0
        for worker in production_system.workers.values():
            wrk_labels.append(worker.worker_id)
            history = worker.status_history
            for idx in range(len(history) - 1):
                t_start, s = history[idx]
                t_end, _ = history[idx + 1]
                if t_end <= t_start:
                    continue
                left = mdates.date2num(datetime.fromtimestamp(t_start, tz=timezone.utc))  # tz=timezone.utc
                width = (t_end - t_start) / 86400  # seconds to days
                color = worker_status_colors.get(s, "#cccccc")
                ax_wrk.barh(wrk_y, width, left=left, color=color, edgecolor='black', height=0.8)
                ax_wrk.text(left + width / 2, wrk_y, s, va='center', ha='center', fontsize=6, color='black')
            wrk_y += 1
        ax_wrk.set_yticks(range(len(wrk_labels)))
        ax_wrk.set_yticklabels(wrk_labels)
        ax_wrk.invert_yaxis()
        ax_wrk.grid(axis='x', linestyle=':', alpha=0.5)

        # --- Format x-axis as date/time ---
        def unix_to_str(ts):
            return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")  # tz=timezone.utc
        # Set custom formatter
        ax_wrk.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax_wrk.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: unix_to_str(mdates.num2date(x, tz=timezone.utc).timestamp()))
        )
        # Get all timestamps for x-axis limits
        all_ts = []
        for ws in production_system.workstations.values():
            all_ts += [t for t, _ in ws.status_history]
        for worker in production_system.workers.values():
            all_ts += [t for t, _ in worker.status_history]
        if all_ts:
            t_min, t_max = min(all_ts), max(all_ts)
            if t_min == t_max:
                # Only one timestamp, show a 1-day window
                t_min_dt = datetime.fromtimestamp(t_min, tz=timezone.utc)
                t_max_dt = datetime.fromtimestamp(t_min + 86400, tz=timezone.utc)
                #t_max_dt = t_min_dt.replace(hour=0, minute=0, second=0, microsecond=0)  # start of day
                #t_max_dt = t_max_dt.replace(hour=t_max_dt.hour + 1)  # next hour
                ax_wrk.set_xlim(
                    mdates.date2num(t_min_dt),
                    mdates.date2num(t_max_dt)
                )
            else:
                ax_wrk.set_xlim(
                    mdates.date2num(datetime.fromtimestamp(t_min, tz=timezone.utc)),
                    mdates.date2num(datetime.fromtimestamp(t_max, tz=timezone.utc))
                )
            fig.autofmt_xdate(rotation=30)
        else:
            # No timestamps at all, show today as default
            now = datetime.now(tz=timezone.utc)
            in_1_hr = now.replace(hour=now.hour+1, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
            #tomorrow = tomorrow.replace(day=tomorrow.day + 1)
            ax_wrk.set_xlim(
                mdates.date2num(now),
                mdates.date2num(in_1_hr)
            )

        #ax_ws.set_ylabel("Workstations")
        #ax_wrk.set_ylabel("Workers")
        ax_wrk.set_xlabel("Time")

        if fig is None:
            return fig
'''
            

class TimeSeriesPlotter:
    """
    Plots interactive time series using Plotly, with tooltips on hover.
    """

    @staticmethod
    def plot_time_series(series_dict, ylabel="Value", title="Time Series"):
        """
        Returns HTML for a Plotly time series plot.

        Args:
            series_dict: dict of {label: [(timestamp, value), ...]}
            ylabel: y-axis label
            title: plot title

        Returns:
            HTML string to embed in a QWebEngineView.
        """
        #print(f"plan_visualizer.py: plotting {title}...")

        local_tz = tzlocal.get_localzone()  # Get the local timezone

        fig = go.Figure()
        for label, data in series_dict.items():
            if not data:
                continue
            ts, vals = zip(*data)
            # Convert UNIX timestamps to ISO format for Plotly
            #x = [datetime.fromtimestamp(t, tz=timezone.utc) for t in ts]
            x = [datetime.fromtimestamp(t, tz=local_tz) for t in ts]
            fig.add_trace(go.Scatter(
                x=x,
                y=vals,
                mode='lines+markers',
                name=label,
                hovertemplate=f"{label}<br>%{{x|%d.%m.%Y %H:%M}}<br>{ylabel}: %{{y:.2f}}<extra></extra>",
                showlegend=False
            ))

        fig.update_layout(
            title=title,
            xaxis_title="Time",
            yaxis_title=ylabel,
            hovermode="closest", # "x unified"
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, itemsizing='constant', font=dict(size=10)),
            margin=dict(l=40, r=20, t=60, b=40),
            template="plotly_white"
        )
        # Hide legend if you want only hover info:
        fig.update_layout(showlegend=False)

        # Return HTML string
        return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

'''
class TimeSeriesPlotter:
    """
    Plots time series data (e.g., utilization, buffer fill level) as a line plot.
    Assumes input is a dict of {label: [(timestamp, value), ...]} for each series.
    The x-axis is formatted as in the Gantt chart (absolute time).
    """

    @staticmethod
    def plot_time_series(series_dict, ylabel="Value", title="Time Series", fig=None):
        """
        Plots one or more time series on a single figure.

        Args:
            series_dict: dict of {label: [(timestamp, value), ...]}
            ylabel: label for the y-axis
            title: plot title
            fig: optional matplotlib Figure to plot into
        """
        if fig is None:
            fig, ax = plt.subplots(figsize=(16, 8))
        else:
            fig.clear()
            ax = fig.add_subplot(111)

        for label, data in series_dict.items():
            if not data:
                continue
            # Unpack timestamps and values
            ts, vals = zip(*data)
            # Convert UNIX timestamps to matplotlib date numbers
            x = [mdates.date2num(datetime.fromtimestamp(t, tz=timezone.utc)) for t in ts]
            ax.plot(x, vals, label=label)

        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Time")
        ax.legend(loc="best")

        # Format x-axis as date/time
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: datetime.fromtimestamp(mdates.num2date(x, tz=timezone.utc).timestamp()).strftime("%d.%m.%Y %H:%M"))
        )
        fig.autofmt_xdate(rotation=30)

        # Set x-limits if any data is present
        all_ts = [t for data in series_dict.values() for t, _ in data]
        if all_ts:
            t_min, t_max = min(all_ts), max(all_ts)
            if t_min == t_max:
                t_min_dt = datetime.fromtimestamp(t_min, tz=timezone.utc)
                t_max_dt = datetime.fromtimestamp(t_min + 86400, tz=timezone.utc)
                ax.set_xlim(mdates.date2num(t_min_dt), mdates.date2num(t_max_dt))
            else:
                ax.set_xlim(
                    mdates.date2num(datetime.fromtimestamp(t_min, tz=timezone.utc)),
                    mdates.date2num(datetime.fromtimestamp(t_max, tz=timezone.utc))
                )
        else:
            now = datetime.now(tz=timezone.utc)
            in_1_hr = now.replace(hour=now.hour+1, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
            ax.set_xlim(mdates.date2num(now), mdates.date2num(in_1_hr))

        return fig
'''