const header = document.querySelector("[data-site-header]");
const root = document.documentElement;
const themeToggle = document.querySelector("[data-theme-toggle]");
const themeToggleLabel = document.querySelector("[data-theme-toggle-label]");
const themeColor = document.querySelector('meta[name="theme-color"]');
const railLinks = document.querySelectorAll("[data-rail-link]");

const themeMeta = {
  dark: "#070809",
  light: "#f6f4ee",
};

const readStoredTheme = () => {
  try {
    return localStorage.getItem("theme");
  } catch {
    return null;
  }
};

const storeTheme = (theme) => {
  try {
    localStorage.setItem("theme", theme);
  } catch {
    // Theme switching should keep working even when storage is unavailable.
  }
};

const applyTheme = (theme) => {
  const nextTheme = theme === "light" ? "light" : "dark";

  root.dataset.theme = nextTheme;
  storeTheme(nextTheme);

  if (themeColor) {
    themeColor.setAttribute("content", themeMeta[nextTheme]);
  }

  if (themeToggle) {
    const isLight = nextTheme === "light";
    themeToggle.setAttribute("aria-pressed", String(isLight));
    themeToggle.setAttribute(
      "aria-label",
      isLight ? "切换到深色主题" : "切换到亮色主题"
    );
  }

  if (themeToggleLabel) {
    themeToggleLabel.textContent = nextTheme === "light" ? "Light" : "Dark";
  }
};

applyTheme(readStoredTheme());

themeToggle?.addEventListener("click", () => {
  applyTheme(root.dataset.theme === "light" ? "dark" : "light");
});

const updateHeader = () => {
  if (!header) return;
  header.toggleAttribute("data-scrolled", window.scrollY > 16);
};

updateHeader();
window.addEventListener("scroll", updateHeader, { passive: true });

const sections = document.querySelectorAll(".section-observe");
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.16 }
);

sections.forEach((section) => observer.observe(section));

const railTargets = [...railLinks]
  .map((link) => {
    const id = link.getAttribute("data-rail-link");
    return id ? document.getElementById(id) : null;
  })
  .filter(Boolean);

const setActiveRail = (id) => {
  railLinks.forEach((link) => {
    link.classList.toggle("is-active", link.getAttribute("data-rail-link") === id);
  });
};

const updateActiveRail = () => {
  if (!railTargets.length) return;

  const anchor = window.scrollY + window.innerHeight * 0.38;
  let active = railTargets[0];

  railTargets.forEach((target) => {
    if (target.offsetTop <= anchor) {
      active = target;
    }
  });

  setActiveRail(active.id);
};

updateActiveRail();
window.addEventListener("scroll", updateActiveRail, { passive: true });
window.addEventListener("resize", updateActiveRail);
