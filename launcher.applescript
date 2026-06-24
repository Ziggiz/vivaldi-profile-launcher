-- Vivaldi Profile Launcher – GUI frontend
--
-- A thin layer over the core CLI (vivaldi_profiles.py). All logic lives in the
-- CLI; this file shows a search box + a select window and calls the right command.
--
-- The app is self-contained: the CLI (vivaldi_profiles.py) lives inside the .app
-- bundle and is located via the app's own bundle path, so the project folder can
-- be moved or deleted without breaking the app.

property PY : "/usr/bin/python3"
property NEW_PROFILE_LABEL : "➕ Create new profile …"
property NEW_SEARCH_LABEL : "🔍 New search …"

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

-- Split a query into non-empty, space-separated words.
on splitWords(q)
	set AppleScript's text item delimiters to " "
	set parts to text items of q
	set AppleScript's text item delimiters to ""
	set out to {}
	repeat with p in parts
		set p to (p as text)
		if p is not "" then set end of out to p
	end repeat
	return out
end splitWords

-- Filter names: keep a name if it contains EVERY word of the query
-- (case-insensitive substring match). Empty query returns all names.
on filterNames(allNames, query)
	set wordList to splitWords(query)
	if (count of wordList) is 0 then return allNames
	set out to {}
	repeat with nm in allNames
		set nmStr to (nm as text)
		set keep to true
		repeat with w in wordList
			-- AppleScript text comparison ignores case by default.
			if nmStr does not contain (w as text) then
				set keep to false
				exit repeat
			end if
		end repeat
		if keep then set end of out to nmStr
	end repeat
	return out
end filterNames

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

-- Prompt for a new profile name (optionally prefilled) and create it.
on promptCreate(prefill)
	set dlg to display dialog "Name of the new profile:" default answer prefill with title "New Vivaldi profile"
	set newName to text returned of dlg
	if newName is not "" then createProfile(newName)
end promptCreate

on run
	set allNames to fetchProfileNames()

	repeat
		-- 1. Ask for a search term (type any word that appears in the name).
		set dlg to display dialog "Search profiles by any word in the name" & return & "(leave empty to list all):" default answer "" with title "Vivaldi Profiles" buttons {"Cancel", "New profile …", "Search"} default button "Search"
		set btn to button returned of dlg
		set query to text returned of dlg

		if btn is "Cancel" then return
		if btn is "New profile …" then
			promptCreate(query)
			return
		end if

		-- 2. Filter and present matches.
		set matches to filterNames(allNames, query)

		if (count of matches) is 0 then
			set a to display alert "No profiles match “" & query & "”." buttons {"Search again", "Create “" & query & "”"} default button "Search again"
			if button returned of a is "Search again" then
				-- loop again
			else
				promptCreate(query)
				return
			end if
		else
			set choices to matches & {NEW_SEARCH_LABEL, NEW_PROFILE_LABEL}
			set chosen to choose from list choices with prompt "Select a profile (start typing to narrow further):" without multiple selections allowed and empty selection allowed
			if chosen is false then return -- cancelled
			set pick to item 1 of chosen

			if pick is NEW_SEARCH_LABEL then
				-- loop again
			else if pick is NEW_PROFILE_LABEL then
				promptCreate(query)
				return
			else
				openProfile(pick)
				return
			end if
		end if
	end repeat
end run
