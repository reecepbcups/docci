package main

import (
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"time"

	"golang.org/x/mod/semver"
)

var (
	RunCheckInterval   = 24 * time.Hour
	howToInstallBinary = "git clone https://github.com/reecepbcups/docci.git docci --depth=1 -b __VERSION__ && cd docci && task install && cd ../.. && rm -rf docci"
	BinaryToGHApi      = "https://api.github.com/repos/reecepbcups/docci/releases"
)

type (
	Release struct {
		Id          int64   `json:"id"`
		Name        string  `json:"name"`
		TagName     string  `json:"tag_name"`
		PublishedAt string  `json:"published_at"`
		Assets      []Asset `json:"assets"`

		Prerelease bool `json:"prerelease"`
		Draft      bool `json:"draft"`
	}
	Asset struct {
		URL      string `json:"url"`
		ID       int    `json:"id"`
		NodeID   string `json:"node_id"`
		Name     string `json:"name"`
		Label    string `json:"label"`
		Uploader struct {
			Login             string `json:"login"`
			ID                int    `json:"id"`
			NodeID            string `json:"node_id"`
			AvatarURL         string `json:"avatar_url"`
			GravatarID        string `json:"gravatar_id"`
			URL               string `json:"url"`
			HTMLURL           string `json:"html_url"`
			FollowersURL      string `json:"followers_url"`
			FollowingURL      string `json:"following_url"`
			GistsURL          string `json:"gists_url"`
			StarredURL        string `json:"starred_url"`
			SubscriptionsURL  string `json:"subscriptions_url"`
			OrganizationsURL  string `json:"organizations_url"`
			ReposURL          string `json:"repos_url"`
			EventsURL         string `json:"events_url"`
			ReceivedEventsURL string `json:"received_events_url"`
			Type              string `json:"type"`
			SiteAdmin         bool   `json:"site_admin"`
		} `json:"uploader"`
		ContentType        string    `json:"content_type"`
		State              string    `json:"state"`
		Size               int       `json:"size"`
		DownloadCount      int       `json:"download_count"`
		CreatedAt          time.Time `json:"created_at"`
		UpdatedAt          time.Time `json:"updated_at"`
		BrowserDownloadURL string    `json:"browser_download_url"`
	}
)

func GetLatestGithubReleases(apiRepoURL string) ([]Release, error) {
	client := http.Client{
		Timeout: 5 * time.Second,
	}
	req, err := http.NewRequest(http.MethodGet, apiRepoURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/vnd.github.v3+json")

	res, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()

	body, err := io.ReadAll(res.Body)
	if err != nil {
		return nil, err
	}

	// parse response
	var releases []Release
	if err := json.Unmarshal(body, &releases); err != nil {
		return nil, err
	}

	return releases, nil
}

// get latest real releases
// given an array of []Release, find the latest PreRelease and latest non prerelease and return both
func GetRealLatestReleases(r []Release) (string, string) {
	latestPre := ""
	latestOfficial := ""

	for _, rel := range r {
		if rel.Prerelease {
			if latestPre == "" || semver.Compare(latestPre, rel.TagName) < 0 {
				latestPre = rel.TagName
			}
		} else {
			if latestOfficial == "" || semver.Compare(latestOfficial, rel.TagName) < 0 {
				latestOfficial = rel.TagName
			}
		}
	}

	return latestPre, latestOfficial
}

// OutOfDateCheckLog returns true if current version is out of date.
func OutOfDateCheckLog(binName, current, latest string) bool {
	currentVer := current
	if currentVer == "dev" {
		currentVer = "v0.0.0"
	}

	isOutOfDate := semver.Compare(currentVer, latest) < 0
	return isOutOfDate
}

func GetInstallMsg(msg, latestVer string) string {
	return strings.ReplaceAll(msg, "__VERSION__", latestVer)
}
