/*
 
   Copyright 2020 Dynojet Research Inc

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

 */
using System;
using System.Collections.Generic;
using System.Text;

namespace JetdriveSharp
{
	public enum JDUnit
	{
		/// <summary>
		/// Seconds
		/// </summary>
		Time = 0,

		/// <summary>
		/// meters
		/// </summary>
		Distance,

		/// <summary>
		/// kph
		/// </summary>
		Speed,

		/// <summary>
		/// newtons
		/// </summary>
		Force,

		/// <summary>
		/// kw
		/// </summary>
		Power,

		/// <summary>
		/// newton-meters
		/// </summary>
		Torque,

		/// <summary>
		/// C
		/// </summary>
		Temperature,

		/// <summary>
		/// kpa
		/// </summary>
		Pressure,

		/// <summary>
		/// RPM
		/// </summary>
		EngineSpeed,

		/// <summary>
		/// rpm/kph
		/// </summary>
		GearRatio,

		/// <summary>
		/// kph/s
		/// </summary>
		Acceleration,

		/// <summary>
		/// Air Fuel Ratio
		/// </summary>
		AFR,

		/// <summary>
		/// kg/hr
		/// </summary>
		FlowRate,

		/// <summary>
		/// Lambda
		/// </summary>
		Lambda,

		/// <summary>
		/// volts
		/// </summary>
		Volts,

		/// <summary>
		/// Amperes
		/// </summary>
		Amps,

		/// <summary>
		/// Percentage
		/// </summary>
		Percentage,

		//Reserved for future use...
		/// <summary>
		/// Not used yet, but acceptable - in a later revision, there will be a dynamic units table for this
		/// </summary>
		Extended = 254,

		/// <summary>
		/// No unit specifed/needed (look for unit in name)
		/// </summary>
		NoUnit = 255,
	}
}
