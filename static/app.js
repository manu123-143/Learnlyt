document.addEventListener("DOMContentLoaded",()=>{
  const sidebar=document.getElementById("sidebar");
  const menu=document.getElementById("menuButton");
  if(menu&&sidebar)menu.addEventListener("click",()=>sidebar.classList.toggle("open"));
  document.querySelectorAll(".flash button").forEach(button=>button.addEventListener("click",()=>button.parentElement.remove()));
  document.querySelectorAll("form[data-confirm]").forEach(form=>form.addEventListener("submit",event=>{if(!window.confirm(form.dataset.confirm))event.preventDefault()}));
  const reveal=document.getElementById("revealButton");
  const answer=document.getElementById("cardAnswer");
  const front=document.querySelector(".card-front");
  if(reveal&&answer&&front)reveal.addEventListener("click",()=>{front.classList.add("hidden");answer.classList.add("visible")});
  const backup=document.querySelector('input[name="backup_file"]');
  const backupLabel=document.getElementById("backupLabel");
  if(backup&&backupLabel)backup.addEventListener("change",()=>{if(backup.files.length)backupLabel.textContent=backup.files[0].name});
});
