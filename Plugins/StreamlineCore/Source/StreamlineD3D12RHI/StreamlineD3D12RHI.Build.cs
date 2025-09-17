/*
* Copyright (c) 2022 - 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
*
* NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
* property and proprietary rights in and to this material, related
* documentation and any modifications thereto. Any use, reproduction,
* disclosure or distribution of this material and related documentation
* without an express license agreement from NVIDIA CORPORATION or
* its affiliates is strictly prohibited.
*/
using UnrealBuildTool;
using System.IO;

public class StreamlineD3D12RHI : ModuleRules
{
	public StreamlineD3D12RHI(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;
		

		PublicIncludePaths.AddRange(
			new string[] {
			}
		);

		PrivateIncludePaths.AddRange(
			new string[] {
			}
		);
			
		
		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"StreamlineRHI",
			}
		);

		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				"D3D12RHI",
				"Engine",
				"RenderCore",
				"RHI",
				"RHICore",
				"Streamline",
				"StreamlineRHI",
			}
		);

		AddEngineThirdPartyPrivateStaticDependencies(Target, "DX12");

#if UE_5_5_OR_LATER
		PrivateDefinitions.Add("ENGINE_ID3D12DYNAMICRHI_NEEDS_CMDLIST=1");
#else
		PrivateDefinitions.Add("ENGINE_ID3D12DYNAMICRHI_NEEDS_CMDLIST=0");
#endif
	}
}
