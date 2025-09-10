import base64
import io
from sklearn.preprocessing import OrdinalEncoder
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, roc_curve
from sklearn import metrics
import pandas as pd
import matplotlib
from matplotlib.lines import Line2D
matplotlib.use('Agg')
from matplotlib import pyplot as plt
import seaborn as sns
import numpy as np

def fig_to_base64(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight')
    fig.clf()
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def run_pipeline(csv_path: str):
    # 1) Load + prepare
    df = pd.read_csv(csv_path)
    enc = OrdinalEncoder(categories=[[False, True]])  # False->0, True->1
    df["win"] = enc.fit_transform(df[["win"]])

    X = df[["first_serve_pctg", "double_faults"]].values
    y = df["win"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, train_size=0.8, random_state=42, stratify=y
    )


    # 2) Scatter: train/test in feature space (colored by label)
    fig_scatter, ax = plt.subplots()
    sc1 = ax.scatter(X_train[:,0], X_train[:,1], c=y_train, cmap="bwr",
                     marker="o", alpha=0.6, label="Train")
    sc2 = ax.scatter(X_test[:,0],  X_test[:,1],  c=y_test,  cmap="bwr",
                     marker="x", alpha=0.8, label="Test")
    ax.set_xlabel("First Serve %")
    ax.set_ylabel("Double Faults")
    ax.set_title("Train vs Test in Feature Space")
    legend_elements = [Line2D([0], [0], color='black', marker='o', label='Train', linestyle=''),
                       Line2D([0], [0], color='black', marker='x', label='Test', linestyle=''),
                       Line2D([0], [0], color='blue', marker='s', label='Win', linestyle=''),
                       Line2D([0], [0], color='red', marker='s', label='Loss', linestyle=''),]
    ax.legend(handles=legend_elements)
    scatter_b64 = fig_to_base64(fig_scatter)

    # 3) Fit + predict
    logreg = LogisticRegression(random_state=42)
    logreg.fit(X_train, y_train)
    y_pred = logreg.predict(X_test)

    # 4) Confusion matrix heatmap
    cnf_matrix = metrics.confusion_matrix(y_test, y_pred)
    class_names = ['loss', 'win']
    fig, ax = plt.subplots()
    tick_marks = np.arange(len(class_names))
    plt.xticks(tick_marks, class_names)
    plt.yticks(tick_marks, class_names)
    sns.heatmap(pd.DataFrame(cnf_matrix), annot=True, cmap="YlGnBu", fmt="g")
    ax.xaxis.set_label_position("top")
    plt.tight_layout()
    plt.title("Confusion matrix")
    plt.ylabel("Actual Label")
    plt.xlabel("Predicted Label")
    heatmap_b64 = fig_to_base64(fig)

    #Classification report
    cr = classification_report(y_test, y_pred, target_names=["loss", "win"])

    #AUC curve
    fig_auc, ax = plt.subplots()
    y_pred_proba = logreg.predict_proba(X_test)[:,1]
    fpr, tpr, _ = metrics.roc_curve(y_test, y_pred_proba)
    auc = metrics.roc_auc_score(y_test, y_pred_proba)
    ax.plot(fpr, tpr, label='data 1, auc'+str(auc))
    ax.legend(loc=4)
    auc_b64 = fig_to_base64(fig_auc)

    return {
        "confusion_matrix": cnf_matrix.tolist(),
        "classification_report": cr,
        "heatmap_b64": heatmap_b64,
        "auc_b64": auc_b64,
        "scatter_b64": scatter_b64,
    }
