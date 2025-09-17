// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "FileName.generated.h"

/**
 * 
 */
UCLASS()
class ARCWARE_TEMPLATE_API UFileName : public UObject
{
	GENERATED_BODY()

	public:
	UFUNCTION(BlueprintCallable, Category = "Screenshot")
	static void SetScreenshotPath();

	UFUNCTION(BlueprintCallable, Category = "Screenshot")
	static void TakeScreenshot();

	UFUNCTION(BlueprintCallable, Category = "Screenshot")
	static FString GetScreenshotFilePath();

	UFUNCTION(BlueprintCallable, Category = "Screenshot")
	static void DeleteScreenshotFile(const FString& FullScreenshotPath);

private:
	static FString FullScreenshotPath;
	static FString CreateCustomUUID4();
	
};
