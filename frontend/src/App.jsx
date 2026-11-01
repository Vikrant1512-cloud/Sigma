import { useEffect, useState } from "react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem("sigma_token") || ""
  );
  const [username, setUsername] = useState(
    () => localStorage.getItem("sigma_username") || ""
  );
  const [role, setRole] = useState(
    () => localStorage.getItem("sigma_role") || ""
  );

  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loading, setLoading] = useState(false);

  const [categories, setCategories] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [activity, setActivity] = useState([]);

  const [selectedCategory, setSelectedCategory] = useState("all");
  const [search, setSearch] = useState("");

  const [newCategory, setNewCategory] = useState("");
  const [documentTitle, setDocumentTitle] = useState("");
  const [uploadCategory, setUploadCategory] = useState("");
  const [uploadFile, setUploadFile] = useState(null);

  const [message, setMessage] = useState("");
  const [activeDocument, setActiveDocument] = useState(null);
  const [pdfUrl, setPdfUrl] = useState("");

  const isAdmin = role === "admin";

  async function apiRequest(path, options = {}) {
    const headers = {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };

    const response = await fetch(`${API}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      logout();
      throw new Error("Your session has expired. Please log in again.");
    }

    const contentType = response.headers.get("content-type") || "";

    if (!response.ok) {
      let errorMessage = "Something went wrong.";

      if (contentType.includes("application/json")) {
        const data = await response.json();
        errorMessage = data.detail || errorMessage;
      }

      throw new Error(errorMessage);
    }

    if (contentType.includes("application/json")) {
      return response.json();
    }

    return response;
  }

  async function login(event) {
    event.preventDefault();
    setLoading(true);
    setLoginError("");

    try {
      const response = await fetch(`${API}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: loginUsername,
          password: loginPassword,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed.");
      }

      localStorage.setItem("sigma_token", data.access_token);
      localStorage.setItem("sigma_username", data.username);
      localStorage.setItem("sigma_role", data.role);

      setToken(data.access_token);
      setUsername(data.username);
      setRole(data.role);
      setLoginPassword("");
    } catch (error) {
      setLoginError(error.message);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);

    localStorage.removeItem("sigma_token");
    localStorage.removeItem("sigma_username");
    localStorage.removeItem("sigma_role");

    setToken("");
    setUsername("");
    setRole("");
    setCategories([]);
    setDocuments([]);
    setActivity([]);
    setPdfUrl("");
    setActiveDocument(null);
  }

  async function loadLibrary() {
    try {
      const [categoryData, documentData] = await Promise.all([
        apiRequest("/api/categories"),
        apiRequest("/api/documents"),
      ]);

      setCategories(categoryData);
      setDocuments(documentData);

      if (categoryData.length > 0) {
        setUploadCategory(String(categoryData[0].id));
      }
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function loadActivity() {
    try {
      const data = await apiRequest("/api/admin/activity");
      setActivity(data);
    } catch (error) {
      setMessage(error.message);
    }
  }

  useEffect(() => {
    if (!token) return;

    async function initialise() {
      try {
        const user = await apiRequest("/api/me");

        setUsername(user.username);
        setRole(user.role);

        await loadLibrary();

        if (user.role === "admin") {
          await loadActivity();
        }
      } catch {
        logout();
      }
    }

    initialise();
  }, [token]);

  async function createCategory(event) {
    event.preventDefault();

    try {
      await apiRequest("/api/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newCategory }),
      });

      setNewCategory("");
      setMessage("Category created successfully.");
      await loadLibrary();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function uploadDocument(event) {
    event.preventDefault();

    if (!uploadFile) {
      setMessage("Please select a PDF.");
      return;
    }

    const formData = new FormData();
    formData.append("title", documentTitle);
    formData.append("category_id", uploadCategory);
    formData.append("file", uploadFile);

    try {
      await apiRequest("/api/documents", {
        method: "POST",
        body: formData,
      });

      setDocumentTitle("");
      setUploadFile(null);
      event.target.reset();

      setMessage("PDF uploaded successfully.");
      await loadLibrary();
      await loadActivity();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function openPdf(document) {
    try {
      const response = await apiRequest(
        `/api/documents/${document.id}/file`
      );

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      if (pdfUrl) URL.revokeObjectURL(pdfUrl);

      setPdfUrl(url);
      setActiveDocument(document);
      await loadActivity();
    } catch (error) {
      setMessage(error.message);
    }
  }

  function closePdf() {
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);

    setPdfUrl("");
    setActiveDocument(null);
  }

  async function deleteDocument(document) {
    if (!window.confirm(`Delete "${document.title}" permanently?`)) {
      return;
    }

    try {
      await apiRequest(`/api/documents/${document.id}`, {
        method: "DELETE",
      });

      setMessage("Document deleted.");
      await loadLibrary();
      await loadActivity();
    } catch (error) {
      setMessage(error.message);
    }
  }

  const filteredDocuments = documents.filter((document) => {
    const matchesCategory =
      selectedCategory === "all" ||
      String(document.category_id) === selectedCategory;

    const matchesSearch =
      document.title.toLowerCase().includes(search.toLowerCase()) ||
      document.category.toLowerCase().includes(search.toLowerCase());

    return matchesCategory && matchesSearch;
  });

  // LOGIN PAGE

  if (!token) {
    return (
      <main className="login-page">
        <div className="login-decoration decoration-one" />
        <div className="login-decoration decoration-two" />

        <section className="login-card">
          <div className="sigma-symbol">Σ</div>

          <p className="eyebrow">PRIVATE MATHEMATICS SPACE</p>
          <h1>Welcome to Sigma.</h1>

          <p className="login-description">
            A focused space to practise, explore and master mathematics.
          </p>

          <form onSubmit={login} className="login-form">
            <label>USERNAME</label>
            <input
              value={loginUsername}
              onChange={(e) => setLoginUsername(e.target.value)}
              placeholder="Enter your username"
              autoComplete="username"
              required
            />

            <label>PASSWORD</label>
            <input
              type="password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
              required
            />

            {loginError && (
              <p className="error-message">{loginError}</p>
            )}

            <button className="primary-button" disabled={loading}>
              {loading ? "Signing in..." : "Enter Sigma"}
              <span>↗</span>
            </button>
          </form>

          <p className="login-footer">
            SIGMA · A PRIVATE LEARNING ENVIRONMENT
          </p>
        </section>
      </main>
    );
  }

  // DASHBOARD

  return (
    <main className="dashboard">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-symbol">Σ</span>
          <span>SIGMA</span>
        </div>

        <div className="sidebar-section">
          <p className="sidebar-label">WORKSPACE</p>

          <button
            className="sidebar-link active"
            onClick={() => {
              closePdf();
              setSelectedCategory("all");
            }}
          >
            <span>▦</span> Library
          </button>

          {isAdmin && (
            <button
              className="sidebar-link"
              onClick={loadActivity}
            >
              <span>◷</span> Activity
            </button>
          )}
        </div>

        <div className="sidebar-bottom">
          <div className="user-profile">
            <div className="avatar">
              {username.charAt(0).toUpperCase()}
            </div>

            <div>
              <strong>{username}</strong>
              <small>{isAdmin ? "Administrator" : "Student"}</small>
            </div>
          </div>

          <button className="logout-button" onClick={logout}>
            Sign out ↗
          </button>
        </div>
      </aside>

      <section className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h1>{activeDocument ? activeDocument.title : "Library"}</h1>
          </div>

          <div className="topbar-right">
            <span className="status-dot" />
            <span>{isAdmin ? "Admin access" : "Student access"}</span>
          </div>
        </header>

        {message && (
          <div className="message-banner">
            {message}
            <button onClick={() => setMessage("")}>×</button>
          </div>
        )}

        {activeDocument ? (
          <section className="pdf-section">
            <div className="pdf-toolbar">
              <button className="secondary-button" onClick={closePdf}>
                ← Back to library
              </button>
              <span>{activeDocument.title}</span>
            </div>

            <iframe
              className="pdf-viewer"
              src={pdfUrl}
              title={activeDocument.title}
            />
          </section>
        ) : (
          <>
            <section className="welcome-row">
              <div>
                <h2>Your mathematics library.</h2>
                <p>
                  Everything you need to learn, practise and improve.
                </p>
              </div>

              <div className="document-count">
                <strong>{documents.length}</strong>
                <span>DOCUMENTS</span>
              </div>
            </section>

            {isAdmin && (
              <section className="admin-grid">
                <form className="admin-card" onSubmit={uploadDocument}>
                  <div className="card-heading">
                    <span className="card-icon">↑</span>
                    <div>
                      <h3>Upload a document</h3>
                      <p>Add a PDF to your library.</p>
                    </div>
                  </div>

                  <input
                    placeholder="Document title"
                    value={documentTitle}
                    onChange={(e) => setDocumentTitle(e.target.value)}
                    required
                  />

                  <select
                    value={uploadCategory}
                    onChange={(e) => setUploadCategory(e.target.value)}
                    required
                  >
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>

                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={(e) => setUploadFile(e.target.files[0])}
                    required
                  />

                  <button className="primary-button">
                    Upload PDF ↗
                  </button>
                </form>

                <form className="admin-card" onSubmit={createCategory}>
                  <div className="card-heading">
                    <span className="card-icon">＋</span>
                    <div>
                      <h3>Create a category</h3>
                      <p>Organise your mathematics resources.</p>
                    </div>
                  </div>

                  <input
                    placeholder="New category name"
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    required
                  />

                  <button className="primary-button">
                    Create category ↗
                  </button>
                </form>
              </section>
            )}

            <section className="library-section">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">EXPLORE</p>
                  <h2>All resources</h2>
                </div>

                <input
                  className="search-input"
                  placeholder="Search resources..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              <div className="category-list">
                <button
                  className={
                    selectedCategory === "all"
                      ? "category active"
                      : "category"
                  }
                  onClick={() => setSelectedCategory("all")}
                >
                  All resources
                </button>

                {categories.map((category) => (
                  <button
                    key={category.id}
                    className={
                      selectedCategory === String(category.id)
                        ? "category active"
                        : "category"
                    }
                    onClick={() =>
                      setSelectedCategory(String(category.id))
                    }
                  >
                    {category.name}
                  </button>
                ))}
              </div>

              {filteredDocuments.length === 0 ? (
                <div className="empty-state">
                  <div>▤</div>
                  <h3>No documents found</h3>
                  <p>
                    {documents.length === 0
                      ? "Your library is empty. Upload your first PDF."
                      : "Try changing your search or category."}
                  </p>
                </div>
              ) : (
                <div className="document-grid">
                  {filteredDocuments.map((document) => (
                    <article className="document-card" key={document.id}>
                      <div className="document-icon">PDF</div>

                      <div className="document-info">
                        <span className="document-category">
                          {document.category}
                        </span>

                        <h3>{document.title}</h3>

                        <small>
                          Added{" "}
                          {new Date(document.created_at).toLocaleDateString()}
                        </small>
                      </div>

                      <div className="document-actions">
                        <button
                          className="open-button"
                          onClick={() => openPdf(document)}
                        >
                          Open ↗
                        </button>

                        {isAdmin && (
                          <button
                            className="delete-button"
                            onClick={() => deleteDocument(document)}
                            title="Delete document"
                          >
                            ×
                          </button>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {isAdmin && (
              <section className="activity-section">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">ADMINISTRATION</p>
                    <h2>Recent activity</h2>
                  </div>

                  <button
                    className="secondary-button"
                    onClick={loadActivity}
                  >
                    Refresh
                  </button>
                </div>

                <div className="activity-table-wrapper">
                  <table className="activity-table">
                    <thead>
                      <tr>
                        <th>USER</th>
                        <th>ROLE</th>
                        <th>ACTION</th>
                        <th>DETAILS</th>
                        <th>TIME</th>
                      </tr>
                    </thead>

                    <tbody>
                      {activity.map((item, index) => (
                        <tr key={index}>
                          <td>{item.username}</td>
                          <td>{item.role}</td>
                          <td>{item.action}</td>
                          <td>{item.details}</td>
                          <td>
                            {new Date(item.created_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}

                      {activity.length === 0 && (
                        <tr>
                          <td colSpan="5">No activity recorded yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}