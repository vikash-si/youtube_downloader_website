// YouTube Downloader Frontend
document.addEventListener('DOMContentLoaded', function() {
    // The frontend is served by Live Server on port 5500 while FastAPI runs on
    // port 8000. Set `window.API_BASE_URL` before this script to override this
    // for another deployment environment.
    const apiBaseUrl = window.API_BASE_URL || 'http://127.0.0.1:8000';
    const urlInput = document.getElementById('youtube-url');
    const getVideoBtn = document.getElementById('get-video-btn');
    const videoInfo = document.getElementById('video-info');
    const thumbnail = document.getElementById('thumbnail');
    const title = document.getElementById('title');
    const duration = document.getElementById('duration');
    const formatsContainer = document.getElementById('formats-container');
    const outputFormat = document.getElementById('output-format');
    const outputFormatHelp = document.getElementById('output-format-help');
    const downloadBtn = document.getElementById('download-btn');
    const errorMessage = document.getElementById('error-message');
    const downloadSection = document.getElementById('download-section');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    let currentUrl = '';
    let selectedFormatId = '';
    let selectedQuality = '';
    let selectedOutputFormat = outputFormat.value;

    outputFormat.addEventListener('change', function() {
        selectedOutputFormat = this.value;
        const isAudio = ['mp3', 'aac'].includes(selectedOutputFormat);
        outputFormatHelp.textContent = isAudio
            ? 'Audio only: the selected video quality is ignored.'
            : 'The selected video quality will be saved in this file type.';
    });

    // Get video info
    getVideoBtn.addEventListener('click', async function() {
        const url = urlInput.value.trim();
        
        if (!url) {
            showError('Please enter a YouTube URL');
            return;
        }

        showLoading(true);
        hideError();

        try {
            const response = await fetch(`${apiBaseUrl}/api/info`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url })
            });

            if (!response.ok) {
                throw new Error(await getErrorMessage(response, 'Failed to fetch video info'));
            }

            const data = await response.json();
            displayVideoInfo(data);
        } catch (error) {
            showError('Error fetching video info: ' + error.message);
        } finally {
            showLoading(false);
        }
    });

    // Display video information
    function displayVideoInfo(data) {
        currentUrl = urlInput.value.trim();
        title.textContent = data.title;
        thumbnail.src = data.thumbnail || '';
        duration.textContent = formatDuration(data.duration);

        formatsContainer.innerHTML = '';
        selectedFormatId = '';
        selectedQuality = '';
        
        if (data.formats && data.formats.length > 0) {
            data.formats.forEach(format => {
                const formatElement = document.createElement('div');
                formatElement.className = 'format-option';
                formatElement.innerHTML = `
                    <input type="radio" id="format-${format.format_id}" name="quality" value="${format.format_id}">
                    <label for="format-${format.format_id}">
                        <span class="quality">${format.quality}</span>
                        ${format.filesize > 0 ? `<span class="size">Estimated download size: ~${formatFileSize(format.filesize)}</span>` : ''}
                    </label>
                `;
                
                formatElement.addEventListener('click', function() {
                    document.querySelectorAll('.format-option input').forEach(input => {
                        input.checked = false;
                    });
                    this.querySelector('input').checked = true;
                    selectedFormatId = format.format_id;
                    selectedQuality = format.quality;
                });
                
                formatsContainer.appendChild(formatElement);
            });
            
            videoInfo.classList.remove('hidden');
            downloadSection.classList.remove('hidden');
        } else {
            showError('No compatible formats found for this video');
        }
    }

    // Download video
    downloadBtn.addEventListener('click', async function() {
        if (!selectedFormatId) {
            showError('Please select a quality option');
            return;
        }

        showLoading(true);
        hideError();
        progressContainer.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressText.textContent = 'Preparing download…';

        try {
            const startResponse = await fetch(`${apiBaseUrl}/api/download/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: currentUrl,
                    format_id: selectedFormatId,
                    quality: selectedQuality,
                    output_format: selectedOutputFormat
                })
            });

            if (!startResponse.ok) {
                throw new Error(await getErrorMessage(startResponse, 'Download failed'));
            }

            const { job_id: jobId } = await startResponse.json();
            await waitForDownload(jobId);
            const response = await fetch(`${apiBaseUrl}/api/download/${jobId}/file`);
            if (!response.ok) {
                throw new Error(await getErrorMessage(response, 'Download failed'));
            }

            // Keep the completed yt-dlp progress visible while the finalized
            // file is handed to the browser for the Save dialog.
            progressText.textContent = 'Sending file to browser…';
            const blob = await readDownloadResponse(response);
            if (blob.size === 0) {
                throw new Error('The server returned an empty media file');
            }
            progressBar.style.width = '100%';
            progressText.textContent = 'Download ready';
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${title.textContent}.${selectedOutputFormat}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            // Show success message
            showSuccess('Download completed successfully!');
        } catch (error) {
            showError('Download failed: ' + error.message);
        } finally {
            showLoading(false);
            progressContainer.classList.add('hidden');
        }
    });

    // Helper functions
    async function waitForDownload(jobId) {
        while (true) {
            const response = await fetch(`${apiBaseUrl}/api/download/${jobId}/status`);
            if (!response.ok) {
                throw new Error(await getErrorMessage(response, 'Unable to check download progress'));
            }

            const job = await response.json();
            if (job.status === 'failed') {
                throw new Error(job.error || 'Download failed');
            }
            if (job.status === 'completed') {
                progressBar.style.width = '100%';
                progressText.textContent = 'Preparing file for browser…';
                return;
            }

            const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
            progressBar.style.width = `${progress}%`;
            progressText.textContent = progress > 0
                ? `Downloading video… ${Math.round(progress)}%`
                : 'Preparing video…';
            await new Promise(resolve => setTimeout(resolve, 200));
        }
    }

    async function readDownloadResponse(response) {
        const contentLength = Number(response.headers.get('content-length'));
        if (!response.body) {
            return response.blob();
        }

        const reader = response.body.getReader();
        const chunks = [];
        let received = 0;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            chunks.push(value);
            received += value.length;
            // The progress bar represents the yt-dlp job, which is already
            // complete. Do not reset it while the browser receives the file.
            if (!contentLength) {
                progressText.textContent = `Sending file to browser… ${formatFileSize(received)}`;
            }
        }

        return new Blob(chunks, { type: response.headers.get('content-type') || 'application/octet-stream' });
    }

    async function getErrorMessage(response, fallback) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            const errorData = await response.json();
            return errorData.detail || fallback;
        }

        return fallback;
    }

    function formatDuration(seconds) {
        if (!seconds || seconds <= 0) return '00:00';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function showLoading(show) {
        getVideoBtn.disabled = show;
        downloadBtn.disabled = show;
        if (show) {
            getVideoBtn.textContent = 'Loading...';
        } else {
            getVideoBtn.textContent = 'Get Video';
        }
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }

    function showSuccess(message) {
        errorMessage.textContent = message;
        errorMessage.className = 'success';
        errorMessage.classList.remove('hidden');
        setTimeout(() => {
            errorMessage.classList.add('hidden');
        }, 3000);
    }
});
