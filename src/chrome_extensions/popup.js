document.getElementById('captureBtn').addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const currentUrl = tab.url;

    if (!currentUrl) {
        showStatus("No valid URL found!", "error");
        return;
    }

    showStatus("Sending to Echo-Fetch...", "");

    try {
        await fetch('http://localhost:5000/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'add_download', url: currentUrl, filename: tab.title || '' })
        });
        showStatus("✓ Sent successfully!", "success");
        setTimeout(() => document.getElementById('statusDiv').style.display = 'none', 3000);
    } catch (error) {
        showStatus("⚠️ Echo-Fetch app not running!", "error");
        console.error("Connection failed:", error);
    }
});

function showStatus(message, type) {
    const statusDiv = document.getElementById('statusDiv');
    statusDiv.textContent = message;
    statusDiv.className = 'status ' + type;
    statusDiv.style.display = 'block';
}