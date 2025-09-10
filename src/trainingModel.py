import base64
import io
from sklearn.preprocessing import OrdinalEncoder
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
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
    Z = df[['first_serve_pctg']].values
    Q = df[['double_faults']].values
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
                       Line2D([0], [0], color='blue', marker='s', label='Loss', linestyle=''),
                       Line2D([0], [0], color='red', marker='s', label='Win', linestyle=''),]
    ax.legend(handles=legend_elements)
    scatter_b64 = fig_to_base64(fig_scatter)

    # 3) Fit + predict
    logreg = LogisticRegression(random_state=42)
    logreg.fit(X_train, y_train)
    y_pred = logreg.predict(X_test)


    # First serve pct sigmoid
    zlogreg = LogisticRegression(random_state=42)
    zlogreg.fit(Z, y)
    z_grid = np.linspace(Z.min()-5, Z.max()+5, 400).reshape(-1,1)
    proba = zlogreg.predict_proba(z_grid)[:,1]
    fig = plt.figure(figsize=[8,8])
    plt.scatter(Z, y, alpha=0.5, label="Matches (0=loss, 1=win)")
    plt.plot(z_grid, proba, label="Sigmoid Curve")
    plt.xlabel("First Serve %")
    plt.ylabel("Win Probability")
    plt.title("Logistic Regression")
    plt.legend()
    fs_sigmoid64 = fig_to_base64(fig)

    # Double Fault sigmoid
    qlogreg = LogisticRegression(random_state=42)
    qlogreg.fit(Q, y)
    q_grid = np.linspace(Q.min()-5, Q.max()+5, 400).reshape(-1,1)
    proba = qlogreg.predict_proba(q_grid)[:,1]
    fig = plt.figure(figsize=[8,8])
    plt.scatter(Q, y, alpha=0.5, label="Matches (0=loss, 1=win)")
    plt.plot(q_grid, proba, label="Sigmoid Curve")
    plt.xlabel("Double Faults")
    plt.ylabel("Win Probability")
    plt.title("Logistic Regression")
    plt.legend()
    df_sigmoid64 = fig_to_base64(fig)

    # Decision Boundary
    clf = make_pipeline(StandardScaler(), LogisticRegression(random_state=42))
    clf.fit(X,y)
    x1 = np.linspace(X[:,0].min() - 2, X[:, 0].max() + 2, 300)
    x2 = np.linspace(X[:,1].min() - 2, X[:,1].max() + 2, 300)
    xx, yy = np.meshgrid(x1, x2)
    grid = np.c_[xx.ravel(), yy.ravel()]
    proba = clf.predict_proba(grid)[:,1].reshape(xx.shape)
    fig, ax = plt.subplots()
    cs = ax.contourf(xx,yy,proba,levels=np.linspace(0,1,11), alpha=0.7)
    ax.contour(xx,yy,proba, levels=[0.5], linewidths=2)
    ax.contour(xx,yy,proba, levels=[0.25, 0.75], linestyles="--")
    ax.scatter(X[y == 0, 0], X[y == 0, 1], marker='o', facecolors='none', edgecolors='k', label='Loss (0)')
    ax.scatter(X[y == 1, 0], X[y == 1, 1], marker='^', label='Win  (1)')
    ax.set_xlabel("First Serve %")
    ax.set_ylabel("Double Faults")
    ax.set_title("Logistic Regression: Decision Boundary & Probability Contours")
    ax.legend(loc="best")
    fig.colorbar(cs, ax=ax, label="P(Win)")
    db64 = fig_to_base64(fig)


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
        "fs_sigmoid64": fs_sigmoid64,
        "df_sigmoid64": df_sigmoid64,
        "db64": db64,
    }
