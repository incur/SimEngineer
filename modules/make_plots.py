from modules.observer import Observer
from modules.tools import convertTime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import plotly.express as px


def plot(observer: Observer):
    plt.rcParams["figure.figsize"] = (10, 10)
    variable_data = {}
    for subject_name, data in observer.subjects.items():
        for variable_name, values in data.variables.items():
            if variable_name not in variable_data:
                variable_data[variable_name] = []
            variable_data[variable_name].append((subject_name, values))

    fig, axes = plt.subplots(len(variable_data))
    fig.subplots_adjust(hspace=0.3)

    x = np.arange(observer.sT)
    x = x / 60
    t = pd.to_datetime(x, unit='m')

    for i, (variable_name, subject_data) in enumerate(variable_data.items()):
        axes[i].set_title(f"{variable_name}")
        for subject_name, values in subject_data:
            axes[i].plot(t, values, label=subject_name)
        axes[i].legend()

        if observer.sT <= 86400:
            x_axis_formatter = DateFormatter('%H:%M:%S')
        else:
            x_axis_formatter = DateFormatter('%d-%H:%M:%S')

        axes[i].xaxis.set_major_formatter(x_axis_formatter)

    plt.show()

def gantt(observer: Observer):
    df = pd.DataFrame(observer.tasks)
    sT = convertTime(observer.sT)
    s = f"1970-01-01 00:00:00"
    e = f"1970-01-01 {sT[0]:02}:{sT[1]:02}:{sT[2]:02}"

    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Resource")
    fig.update_layout(xaxis=dict(title='Timestamp', tickformat = '%H:%M:%S', autorange=True, autorangeoptions=dict(minallowed=s, maxallowed=e) ))
    fig.update_yaxes(autorange="reversed")
    fig.show()
