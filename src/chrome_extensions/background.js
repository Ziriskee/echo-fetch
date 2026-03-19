// Create context menu for right-click links
chrome.contextMenus.create({
    id: "downloadWithEchoFetch",
    title: "🚀 Download with Echo-Fetch",
    contexts: ["link"]
});

// Handle context menu click
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    const linkUrl = info.linkUrl;
    await sendToEchoFetch(linkUrl, info.linkText);
});

async function sendToEchoFetch(url, filename = '') {
    try {
        const response = await fetch('http://localhost:5000/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'add_download', url, filename })
        });
        const result = await response.json();
        console.log("Echo-Fetch Response:", result);
    } catch (error) {
        alert("⚠️ Echo-Fetch App not running!\n\nPlease launch Echo-Fetch first.");
        console.error("Failed to connect:", error);
    }
}