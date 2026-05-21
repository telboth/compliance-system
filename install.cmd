@echo off
:: install.cmd — starter install.ps1 med ExecutionPolicy Bypass.
::
:: Bruk denne filen dersom PowerShell viser:
::   "cannot be loaded because running scripts is disabled on this system"
::
:: Alle argumenter sendes videre til install.ps1, for eksempel:
::   install.cmd -Update
::   install.cmd -Stop
::   install.cmd -Help
::
:: Batch-filer pavirkes ikke av PowerShell execution policy og vil
:: alltid starte selv om policy er satt til Restricted eller AllSigned.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
