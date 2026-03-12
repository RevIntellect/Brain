/**
 * Aaron Wolf — 30/60/90 Day Onboarding Dashboard
 * Google Apps Script Web App
 *
 * Deploy: Extensions > Apps Script > Deploy > New deployment > Web app
 * Set "Execute as: Me" and "Who has access: Anyone" (or your org)
 */

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('Aaron Wolf — 30/60/90 Day Onboarding Dashboard')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1.0');
}
