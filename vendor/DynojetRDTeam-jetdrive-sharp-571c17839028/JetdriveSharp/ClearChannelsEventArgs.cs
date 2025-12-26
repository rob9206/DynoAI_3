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
	public delegate void ClearChannelsHandler(Object sender, ClearChannelsEventArgs e);

	public class ClearChannelsEventArgs : EventArgs
	{
		public UInt16 HostId
		{
			get;private set;
		}

		public String HostName
		{
			get;private set;
		}

		public ClearChannelsEventArgs(UInt16 hostId, String hostName)
		{
			this.HostId = hostId;
			this.HostName = hostName;
		}

	}
}
