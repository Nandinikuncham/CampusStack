import "../css/input.css";

const menuButton = document.querySelector("[data-menu-toggle]");
const menu = document.querySelector("[data-mobile-menu]");

if (menuButton && menu) {
  menuButton.addEventListener("click", () => {
    const isExpanded = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", String(!isExpanded));
    menuButton.setAttribute(
      "aria-label",
      isExpanded ? "Open navigation menu" : "Close navigation menu",
    );
    menu.hidden = isExpanded;
  });

  menu.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.setAttribute("aria-label", "Open navigation menu");
      menu.hidden = true;
    }
  });
}

const year = document.querySelector("[data-current-year]");
if (year) year.textContent = new Date().getFullYear();
