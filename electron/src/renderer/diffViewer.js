import { ipcRenderer } from 'electron';

export async function fetchReportLinks(sessionId) {
  const response = await window.macWinBridge.getConversionStatus(sessionId);
  if (response?.summary?.conversion_report) {
    return response.summary.conversion_report;
  }
  return null;
}
