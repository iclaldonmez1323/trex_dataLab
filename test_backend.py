import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api():
    print("Testing GET / ...")
    r = client.get("/")
    assert r.status_code == 200, f"GET / failed: {r.status_code}"
    print("[OK] GET / OK")

    print("Testing GET /data-quality ...")
    r = client.get("/data-quality")
    assert r.status_code == 200, f"GET /data-quality failed: {r.status_code}"
    print("[OK] GET /data-quality OK")

    print("Testing GET /preprocessing ...")
    r = client.get("/preprocessing")
    assert r.status_code == 200, f"GET /preprocessing failed: {r.status_code}"
    assert "Preprocessing" in r.text
    print("[OK] GET /preprocessing OK")

    print("Testing GET /visualization ...")
    r = client.get("/visualization")
    assert r.status_code == 200, f"GET /visualization failed: {r.status_code}"
    assert "Görselleştirme" in r.text
    print("[OK] GET /visualization OK")

    print("Testing GET /portfolio ...")
    r = client.get("/portfolio")
    assert r.status_code == 200, f"GET /portfolio failed: {r.status_code}"
    assert "Predictive Maintenance" in r.text
    assert "Portfolio" in r.text
    print("[OK] GET /portfolio OK")

    print("Testing 409 without data ...")
    client.delete("/api/reset")
    r = client.get("/api/visualization/overview")
    assert r.status_code == 409, f"Expected 409, got {r.status_code}"
    print("[OK] GET /api/visualization/overview returns 409 when no data loaded")

    print("Testing POST /api/upload with test_data.csv ...")
    with open("test_data.csv", "rb") as f:
        r = client.post("/api/upload", files={"file": ("test_data.csv", f, "text/csv")})
    assert r.status_code == 200, f"Upload failed: {r.status_code} - {r.text}"
    print("[OK] POST /api/upload OK")

    print("Testing GET /api/visualization/overview with loaded data ...")
    r = client.get("/api/visualization/overview")
    assert r.status_code == 200
    data = r.json()
    assert len(data["numeric_columns"]) > 0
    assert len(data["categorical_columns"]) > 0
    assert len(data["suggestions"]) > 0
    assert "matrix" in data["correlation"]
    print(f"[OK] Overview returned {len(data['numeric_columns'])} numeric, {len(data['categorical_columns'])} categorical columns, and {len(data['suggestions'])} suggestions.")

    num_col = data["numeric_columns"][0]
    cat_col = data["categorical_columns"][0]

    # Histogram
    print(f"Testing chart type=histogram for {num_col} ...")
    r = client.get(f"/api/visualization/chart?type=histogram&column={num_col}")
    assert r.status_code == 200
    h_data = r.json()
    assert len(h_data["counts"]) > 0
    assert len(h_data["bin_labels"]) == len(h_data["counts"])
    print("[OK] Histogram OK")

    # Boxplot
    print(f"Testing chart type=boxplot for {num_col} ...")
    r = client.get(f"/api/visualization/chart?type=boxplot&column={num_col}")
    assert r.status_code == 200
    b_data = r.json()
    assert len(b_data["box"]) == 5
    print("[OK] Boxplot OK")

    # Bar
    print(f"Testing chart type=bar for {cat_col} ...")
    r = client.get(f"/api/visualization/chart?type=bar&column={cat_col}")
    assert r.status_code == 200
    bar_data = r.json()
    assert len(bar_data["items"]) > 0
    print("[OK] Bar chart OK")

    # Scatter
    if len(data["numeric_columns"]) >= 2:
        x_col = data["numeric_columns"][0]
        y_col = data["numeric_columns"][1]
        print(f"Testing chart type=scatter for {x_col} vs {y_col} ...")
        r = client.get(f"/api/visualization/chart?type=scatter&x={x_col}&y={y_col}")
        assert r.status_code == 200
        s_data = r.json()
        assert len(s_data["x"]) == len(s_data["y"])
        print("[OK] Scatter OK")

    # Grouped Boxplot
    print(f"Testing chart type=grouped_boxplot for {cat_col} and {num_col} ...")
    r = client.get(f"/api/visualization/chart?type=grouped_boxplot&cat={cat_col}&num={num_col}")
    assert r.status_code == 200
    gb_data = r.json()
    assert len(gb_data["groups"]) > 0
    print("[OK] Grouped Boxplot OK")

    print("\nALL PORTFOLIO, VISUALIZATION, PREPROCESSING & QUALITY TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
