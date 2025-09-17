// Fill out your copyright notice in the Description page of Project Settings.


#include "FileName.h"
#include <random>

FString UFileName::FullScreenshotPath;

void UFileName::SetScreenshotPath()
{
	FString ScreenshotNameUUID4 = CreateCustomUUID4();
	FullScreenshotPath = FPaths::Combine(FPaths::FPaths::ProjectDir(), TEXT("Saved/Screenshots/WindowsEditor"), ScreenshotNameUUID4 + TEXT(".png"));
}

void UFileName::TakeScreenshot()
{
	SetScreenshotPath();
	FScreenshotRequest::RequestScreenshot(FullScreenshotPath, false, false);
}

FString UFileName::GetScreenshotFilePath()
{
	return FullScreenshotPath;
}

void UFileName::DeleteScreenshotFile(const FString& FullFilePath) {

	if (FPlatformFileManager::Get().GetPlatformFile().DeleteFile(*FullFilePath))
	{
		UE_LOG(LogTemp, Warning, TEXT("Deleted file: %s"));
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to delete file: %s"));
	}
}

FString UFileName::CreateCustomUUID4()
{
	FString CustomUUID = "";

	std::random_device rd;
	std::mt19937 gen(rd());
	std::uniform_int_distribution<> dis(0, 15);
	const char* hex_chars = "0123456789abcdef";
	std::string uuid_str = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx";

	for (int i = 0; i < uuid_str.size(); ++i) {
		if (uuid_str[i] == '4') {
			continue; 
		}
		if (uuid_str[i] == 'x') {
			uuid_str[i] = hex_chars[dis(gen)];
		}
		else if (uuid_str[i] == 'y') {
			uuid_str[i] = hex_chars[dis(gen) & 0x3 | 0x8];
		}
	}
	return FString(uuid_str.c_str());
}