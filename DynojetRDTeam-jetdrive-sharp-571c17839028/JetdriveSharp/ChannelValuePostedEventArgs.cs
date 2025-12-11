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
	public class ChannelValuePostedEventArgs : EventArgs
	{
		public JDChannelInfo ChannelInfo
		{
			get;private set;
		}

		public String ProviderName
		{
			get;private set;
		}

		public DateTime Timestamp
		{
			get;private set;
		}

		public float Value
		{
			get;private set;
		}

		public InboundKLHDVMessage Message
		{
			get;private set;
		}

		public UInt16 ChanID
		{
			get;private set;
		}

		public ChannelValuePostedEventArgs(JDChannelInfo info, String providerName, DateTime timestamp, float value, UInt16 chanId, InboundKLHDVMessage msg)
		{
			this.ChannelInfo = info;
			this.ProviderName = providerName;
			this.Timestamp = timestamp;
			this.Value = value;
			this.Message = msg;
			this.ChanID = chanId;
		}



	}
}
