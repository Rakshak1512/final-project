import { useEffect, useRef, useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  FiMenu,
  FiBell,
  FiSearch,
  FiChevronDown,
  FiUser,
  FiSettings,
  FiLogOut,
  FiX,
  FiCalendar,
  FiAward,
  FiFileText,
  FiCheckSquare,
  FiUsers,
  FiArrowRight,
} from "react-icons/fi";
import ThemeToggle from "../common/ThemeToggle.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { useRealtime } from "../../context/RealtimeContext.jsx";
import { notificationService, searchService } from "../../api/services.js";
import { fileUrl, initials } from "../../utils/format.js";

export default function Topbar({ onMenuClick, basePath, onSearch, showSearch = true }) {
  const { user, logout } = useAuth();
  const { isConnected } = useRealtime();
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Global Search State
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const searchContainerRef = useRef(null);
  const debounceTimerRef = useRef(null);
  const latestQueryRef = useRef("");
  const mobileInputRef = useRef(null);

  useEffect(() => {
    if (mobileSearchOpen) {
      setTimeout(() => mobileInputRef.current?.focus(), 80);
    }
  }, [mobileSearchOpen]);

  useEffect(() => {
    let mounted = true;
    notificationService
      .unreadCount()
      .then(({ data }) => mounted && setUnread(data.count ?? data.unread_count ?? 0))
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  // Handle outside click for avatar menu and global search dropdown
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Debounced global search execution with race condition prevention
  const handleSearchChange = (val) => {
    setQuery(val);
    if (onSearch) onSearch(val);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    const trimmed = val.trim();
    latestQueryRef.current = trimmed;
    setSelectedIndex(-1);

    if (!trimmed) {
      setSearchResults([]);
      setSearchOpen(false);
      setSearching(false);
      return;
    }

    setSearching(true);
    setSearchOpen(true);

    debounceTimerRef.current = setTimeout(async () => {
      try {
        const { data } = await searchService.global(trimmed);
        if (latestQueryRef.current === trimmed) {
          setSearchResults(data?.results || []);
        }
      } catch (err) {
        console.error("Global search error:", err);
        if (latestQueryRef.current === trimmed) {
          setSearchResults([]);
        }
      } finally {
        if (latestQueryRef.current === trimmed) {
          setSearching(false);
        }
      }
    }, 220);
  };

  const handleSelectResult = (item) => {
    setSearchOpen(false);
    setMobileSearchOpen(false);
    setQuery("");
    setSelectedIndex(-1);
    if (item.link) {
      navigate(item.link);
    }
  };

  const handleClearSearch = () => {
    setQuery("");
    setSearchResults([]);
    setSearchOpen(false);
    setSelectedIndex(-1);
    latestQueryRef.current = "";
    if (onSearch) onSearch("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      setSearchOpen(false);
      setMobileSearchOpen(false);
      setSelectedIndex(-1);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < searchResults.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : searchResults.length - 1));
    } else if (e.key === "Enter" && searchResults.length > 0) {
      e.preventDefault();
      const target = selectedIndex >= 0 && selectedIndex < searchResults.length
        ? searchResults[selectedIndex]
        : searchResults[0];
      handleSelectResult(target);
    }
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case "Events":
        return <FiCalendar color="#8b5cf6" size={15} />;
      case "Certificates":
        return <FiAward color="#d946ef" size={15} />;
      case "My Registrations":
      case "Student Registrations":
      case "Registrations":
        return <FiFileText color="#3b82f6" size={15} />;
      case "Results & Winners":
        return <FiAward color="#eab308" size={15} />;
      case "Assigned Work":
        return <FiCheckSquare color="#f97316" size={15} />;
      case "Faculty Directory":
        return <FiUsers color="#10b981" size={15} />;
      case "Notifications":
        return <FiBell color="#ec4899" size={15} />;
      default:
        return <FiArrowRight color="#8b5cf6" size={15} />;
    }
  };

  return (
    <header
      className="app-topbar"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 90,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 14,
        padding: "max(12px, env(safe-area-inset-top, 0px)) max(20px, env(safe-area-inset-right, 0px)) 12px max(20px, env(safe-area-inset-left, 0px))",
        background: "var(--bg-glass)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid var(--border-color)",
        width: "100%",
        maxWidth: "100%",
        boxSizing: "border-box",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0, flex: 1 }}>
        <button
          className="topbar-hamburger-btn"
          onClick={onMenuClick}
          aria-label="Toggle navigation menu"
          type="button"
        >
          <FiMenu size={20} />
        </button>

        {/* Real-time WebSocket Live Status Indicator */}
        <div
          className="live-indicator topbar-live-indicator"
          title={isConnected ? "Live Real-Time WebSocket Connected" : "Connecting to Real-Time Service..."}
          style={{
            opacity: isConnected ? 1 : 0.7,
            borderColor: isConnected ? "rgba(16, 185, 129, 0.35)" : "rgba(245, 158, 11, 0.35)",
            background: isConnected ? "rgba(16, 185, 129, 0.1)" : "rgba(245, 158, 11, 0.1)",
            color: isConnected ? "#10b981" : "#f59e0b",
            flexShrink: 0,
          }}
        >
          <span
            className="live-dot"
            style={{
              backgroundColor: isConnected ? "#10b981" : "#f59e0b",
              boxShadow: isConnected ? "0 0 8px #10b981" : "0 0 8px #f59e0b",
            }}
          />
          <span className="topbar-live-text" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 700 }}>
            {isConnected ? "LIVE" : "SYNCING"}
          </span>
        </div>

        {showSearch && (
          <div
            ref={searchContainerRef}
            className="topbar-desktop-search"
            style={{
              position: "relative",
              maxWidth: 380,
              flex: 1,
              minWidth: 0,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                background: "var(--input-bg)",
                border: "1.5px solid var(--border-color)",
                borderRadius: 999,
                padding: "9px 16px",
                width: "100%",
                boxShadow: searchOpen ? "0 0 0 2px rgba(139, 92, 246, 0.25)" : "none",
                transition: "box-shadow 0.2s ease",
              }}
            >
              <FiSearch color="var(--text-muted)" size={16} />
              <input
                value={query}
                onChange={(e) => handleSearchChange(e.target.value)}
                onFocus={() => {
                  if (query.trim()) setSearchOpen(true);
                }}
                onKeyDown={handleKeyDown}
                placeholder="Search events, certificates, registrations..."
                style={{
                  border: "none",
                  background: "transparent",
                  outline: "none",
                  color: "var(--text-primary)",
                  width: "100%",
                  fontSize: 13.5,
                }}
              />
              {query && (
                <button
                  type="button"
                  onClick={handleClearSearch}
                  style={{
                    background: "none",
                    border: "none",
                    padding: 2,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    color: "var(--text-muted)",
                  }}
                  title="Clear search"
                >
                  <FiX size={15} />
                </button>
              )}
            </div>

            {/* Global Search Results Dropdown Overlay */}
            {searchOpen && (
              <div
                className="glass-card"
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  left: 0,
                  right: 0,
                  maxHeight: 400,
                  overflowY: "auto",
                  background: "var(--bg-elevated)",
                  borderRadius: 18,
                  border: "1px solid var(--border-color)",
                  boxShadow: "0 16px 36px rgba(0, 0, 0, 0.25)",
                  zIndex: 100,
                  padding: "8px 0",
                }}
              >
                {searching ? (
                  <div
                    style={{
                      padding: "20px",
                      textAlign: "center",
                      color: "var(--text-secondary)",
                      fontSize: 13,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                    }}
                  >
                    <span className="dot-pulse" /> Searching EventSphere...
                  </div>
                ) : searchResults.length === 0 ? (
                  <div
                    style={{
                      padding: "24px 18px",
                      textAlign: "center",
                      color: "var(--text-secondary)",
                      fontSize: 13,
                    }}
                  >
                    No matching records found for <strong style={{ color: "var(--text-primary)" }}>"{query}"</strong>.
                  </div>
                ) : (
                  <div>
                    <div
                      style={{
                        padding: "6px 16px 8px",
                        fontSize: 11,
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: "var(--text-muted)",
                        borderBottom: "1px solid var(--border-color)",
                      }}
                    >
                      Search Results ({searchResults.length})
                    </div>

                    {searchResults.map((item, idx) => (
                      <div
                        key={idx}
                        onClick={() => handleSelectResult(item)}
                        style={{
                          padding: "10px 16px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 12,
                          cursor: "pointer",
                          background: idx === selectedIndex ? "rgba(139, 92, 246, 0.15)" : "transparent",
                          transition: "background 0.15s ease",
                          borderBottom:
                            idx < searchResults.length - 1
                              ? "1px solid rgba(255, 255, 255, 0.04)"
                              : "none",
                        }}
                        onMouseEnter={(e) => {
                          setSelectedIndex(idx);
                          e.currentTarget.style.background = "rgba(139, 92, 246, 0.15)";
                        }}
                        onMouseLeave={(e) => {
                          if (selectedIndex !== idx) e.currentTarget.style.background = "transparent";
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: 8,
                              background: "rgba(139, 92, 246, 0.12)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            {getCategoryIcon(item.category)}
                          </div>
                          <div style={{ minWidth: 0 }}>
                            <div
                              style={{
                                fontSize: 13.5,
                                fontWeight: 600,
                                color: "var(--text-primary)",
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}
                            >
                              {item.title}
                            </div>
                            {item.subtitle && (
                              <div
                                style={{
                                  fontSize: 11.5,
                                  color: "var(--text-muted)",
                                  whiteSpace: "nowrap",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  marginTop: 2,
                                }}
                              >
                                {item.subtitle}
                              </div>
                            )}
                          </div>
                        </div>

                        {item.badge && (
                          <span
                            style={{
                              fontSize: 10.5,
                              fontWeight: 700,
                              padding: "2px 8px",
                              borderRadius: 6,
                              background: "rgba(139, 92, 246, 0.15)",
                              color: "#8b5cf6",
                              flexShrink: 0,
                            }}
                          >
                            {item.badge}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        {/* Mobile Search Toggle Button */}
        {showSearch && (
          <button
            className="topbar-mobile-search-btn"
            onClick={() => {
              setMobileSearchOpen(true);
              if (query.trim()) setSearchOpen(true);
            }}
            aria-label="Search"
            type="button"
          >
            <FiSearch size={18} />
          </button>
        )}

        <ThemeToggle />

        <Link
          to={`${basePath}/notifications`}
          className="topbar-action-btn"
          aria-label={`Notifications ${unread > 0 ? `(${unread} unread)` : ""}`}
        >
          <FiBell size={18} />
          {unread > 0 && (
            <span
              style={{
                position: "absolute",
                top: -2,
                right: -2,
                background: "var(--danger)",
                color: "#fff",
                fontSize: 10,
                fontWeight: 700,
                borderRadius: "50%",
                minWidth: 17,
                height: 17,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "0 3px",
              }}
            >
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </Link>

        {/* User Profile Dropdown Button */}
        <div ref={menuRef} style={{ position: "relative" }}>
          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="topbar-user-btn"
            aria-label="User profile menu"
            type="button"
          >
            {user?.profile_picture ? (
              <img
                src={fileUrl(user.profile_picture)}
                alt=""
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  objectFit: "cover",
                  flexShrink: 0,
                }}
              />
            ) : (
              <span
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  background: "var(--gradient-primary)",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  fontSize: 14,
                  flexShrink: 0,
                }}
              >
                {initials(user?.name)}
              </span>
            )}
            <span className="topbar-user-name" style={{ fontSize: 14, fontWeight: 600, whiteSpace: "nowrap" }}>
              {user?.name?.split(" ")[0]}
            </span>
            <FiChevronDown size={14} color="var(--text-muted)" style={{ flexShrink: 0 }} />
          </button>

          {menuOpen && (
            <div
              className="glass-card"
              style={{
                position: "absolute",
                right: 0,
                top: "calc(100% + 8px)",
                width: 200,
                borderRadius: 16,
                padding: 6,
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-color)",
                boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
                zIndex: 120,
              }}
            >
              <Link
                to={`${basePath}/profile`}
                onClick={() => setMenuOpen(false)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  borderRadius: 10,
                  color: "var(--text-primary)",
                  fontSize: 13.5,
                  fontWeight: 500,
                }}
              >
                <FiUser size={16} /> Profile
              </Link>
              <Link
                to={`${basePath}/settings`}
                onClick={() => setMenuOpen(false)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  borderRadius: 10,
                  color: "var(--text-primary)",
                  fontSize: 13.5,
                  fontWeight: 500,
                }}
              >
                <FiSettings size={16} /> Settings
              </Link>
              <button
                onClick={logout}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  borderRadius: 10,
                  color: "var(--danger)",
                  fontSize: 13.5,
                  fontWeight: 500,
                  width: "100%",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                <FiLogOut size={16} /> Logout
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Expandable Search Bar Overlay */}
      {mobileSearchOpen && (
        <div
          className="topbar-mobile-search-overlay"
          style={{
            position: "absolute",
            inset: 0,
            background: "var(--bg-elevated)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            zIndex: 110,
            display: "flex",
            alignItems: "center",
            padding: "max(8px, env(safe-area-inset-top, 0px)) 12px 8px",
            gap: 10,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              background: "var(--input-bg)",
              border: "1.5px solid var(--border-color)",
              borderRadius: 999,
              padding: "8px 14px",
              flex: 1,
              minWidth: 0,
            }}
          >
            <FiSearch color="var(--text-muted)" size={16} />
            <input
              ref={mobileInputRef}
              value={query}
              onChange={(e) => handleSearchChange(e.target.value)}
              onFocus={() => {
                if (query.trim()) setSearchOpen(true);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search events, certs..."
              style={{
                border: "none",
                background: "transparent",
                outline: "none",
                color: "var(--text-primary)",
                width: "100%",
                fontSize: 14,
              }}
            />
            {query && (
              <button
                type="button"
                onClick={handleClearSearch}
                style={{
                  background: "none",
                  border: "none",
                  padding: 4,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  color: "var(--text-muted)",
                }}
                title="Clear search"
              >
                <FiX size={16} />
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => {
              setMobileSearchOpen(false);
              setSearchOpen(false);
            }}
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              border: "1px solid var(--border-color)",
              borderRadius: "50%",
              width: 38,
              height: 38,
              minWidth: 38,
              minHeight: 38,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-primary)",
              cursor: "pointer",
              flexShrink: 0,
            }}
            aria-label="Close search"
          >
            <FiX size={18} />
          </button>
        </div>
      )}

      <style>{`
        .topbar-hamburger-btn {
          display: none;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          min-width: 44px;
          min-height: 44px;
          border-radius: 12px;
          background: var(--bg-elevated);
          border: 1px solid var(--border-color);
          color: var(--text-primary);
          cursor: pointer;
          transition: background 0.15s ease, border-color 0.15s ease;
        }
        .topbar-hamburger-btn:hover {
          border-color: #8b5cf6;
        }
        .topbar-action-btn {
          position: relative;
          width: 40px;
          height: 40px;
          min-width: 44px;
          min-height: 44px;
          border-radius: 50%;
          border: 1.5px solid var(--border-color);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-primary);
          background: var(--bg-elevated);
          text-decoration: none;
          transition: border-color 0.15s ease;
        }
        .topbar-action-btn:hover {
          border-color: #8b5cf6;
          color: #8b5cf6;
        }
        .topbar-user-btn {
          display: flex;
          align-items: center;
          gap: 8px;
          background: none;
          border: none;
          color: var(--text-primary);
          cursor: pointer;
          min-height: 44px;
          padding: 2px 4px;
          border-radius: 999px;
        }
        .topbar-mobile-search-btn {
          display: none;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          min-width: 44px;
          min-height: 44px;
          border-radius: 50%;
          border: 1.5px solid var(--border-color);
          color: var(--text-primary);
          background: var(--bg-elevated);
          cursor: pointer;
        }
        @media (max-width: 900px) {
          .topbar-hamburger-btn {
            display: flex !important;
          }
        }
        @media (max-width: 768px) {
          .app-topbar {
            padding: max(10px, env(safe-area-inset-top, 0px)) max(14px, env(safe-area-inset-right, 0px)) 10px max(14px, env(safe-area-inset-left, 0px)) !important;
            gap: 10px !important;
          }
          .topbar-desktop-search {
            display: none !important;
          }
          .topbar-mobile-search-btn {
            display: flex !important;
          }
        }
        @media (max-width: 640px) {
          .topbar-user-name {
            display: none !important;
          }
          .topbar-live-text {
            display: none !important;
          }
          .topbar-live-indicator {
            padding: 5px 8px !important;
          }
        }
        @media (max-width: 380px) {
          .app-topbar {
            padding: max(8px, env(safe-area-inset-top, 0px)) 8px 8px !important;
            gap: 6px !important;
          }
          .topbar-action-btn,
          .topbar-mobile-search-btn {
            width: 36px !important;
            height: 36px !important;
            min-width: 40px !important;
            min-height: 40px !important;
          }
          .topbar-hamburger-btn {
            width: 38px !important;
            height: 38px !important;
            min-width: 40px !important;
            min-height: 40px !important;
          }
        }
      `}</style>
    </header>
  );
}
