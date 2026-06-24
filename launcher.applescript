-- Vivaldi Profile Launcher – GUI frontend
--
-- A thin layer over the core CLI (vivaldi_profiles.py). All logic lives in the
-- CLI; this file only shows a search/select window and calls the right command.
--
-- The app is self-contained: the CLI (vivaldi_profiles.py) lives inside the .app
-- bundle and is located via the app's own bundle path, so the project folder can
-- be moved or deleted without breaking the app.

property PY : "/usr/bin/python3"
property NEW_PROFILE_LABEL : "➕ Create new profile …"

-- Absolute path to the CLI inside this .app bundle.
on cliPath()
	return (POSIX path of (path to me)) & "Contents/Resources/vivaldi_profiles.py"
end cliPath

-- Run a CLI command. Returns {exitCode, stdout}.
on runCLI(cmdArgs)
	set q to quoted form of (cliPath())
	set fullCmd to PY & " " & q & " " & cmdArgs
	try
		set out to do shell script fullCmd
		return {0, out}
	on error errMsg number errNum
		-- do shell script throws on exit != 0; errNum is the exit code.
		return {errNum, errMsg}
	end try
end runCLI

-- Fetch profile names. `list` prints one name per line (alphabetical).
-- Note: do shell script returns line breaks as carriage returns (\r),
-- so we split on `return`, not `linefeed`.
on fetchProfileNames()
	set res to runCLI("list")
	if item 1 of res is not 0 then
		display alert "Could not read profiles" message (item 2 of res) as critical
		return {}
	end if
	set names to item 2 of res
	if names is "" then return {}
	set AppleScript's text item delimiters to return
	set nameList to text items of names
	set AppleScript's text item delimiters to ""
	return nameList
end fetchProfileNames

on openProfile(profileName)
	set res to runCLI("open " & quoted form of profileName)
	if item 1 of res is not 0 then
		display alert "Could not open the profile" message (item 2 of res) as critical
	end if
end openProfile

on createProfile(profileName)
	-- --yes so the CLI doesn't block on input if Vivaldi is running.
	set res to runCLI("create " & quoted form of profileName & " --yes")
	if item 1 of res is not 0 then
		display alert "Could not create the profile" message (item 2 of res) as critical
	end if
end createProfile

on run
	set nameList to fetchProfileNames()
	set choices to {NEW_PROFILE_LABEL} & nameList

	set chosen to choose from list choices with prompt "Select or search for a profile:" without multiple selections allowed and empty selection allowed
	if chosen is false then return -- cancelled
	set pick to item 1 of chosen

	if pick is NEW_PROFILE_LABEL then
		set dlg to display dialog "Name of the new profile:" default answer "" with title "New Vivaldi profile"
		set newName to text returned of dlg
		if newName is not "" then createProfile(newName)
	else
		openProfile(pick)
	end if
end run
