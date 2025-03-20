async function searchSongs() {
    let query = document.getElementById("searchBox").value;
    if (query.length < 2) {
        document.getElementById("suggestions").innerHTML = "";
        return;
    }
    let response = await fetch(`/search?q=${query}`);
    let songTitles = await response.json();
    let suggestionBox = document.getElementById("suggestions");
    suggestionBox.innerHTML = "";
    songTitles.forEach(title => {
        let div = document.createElement("div");
        div.classList.add("list-group-item", "list-group-item-action");
        div.textContent = title;
        div.onclick = () => {
            document.getElementById("searchBox").value = title;
            suggestionBox.innerHTML = "";
        };
        suggestionBox.appendChild(div);
    });
}
