document.getElementById("application-page").addEventListener("change", (event) => {
  window.location.assign(event.target.value);
});
document.getElementById("application-page").disabled = false;
window.addEventListener("pageshow", () => {
  document.getElementById("application-page").value = window.location.pathname.includes("overlay") ? "/overlay" : "/";
});