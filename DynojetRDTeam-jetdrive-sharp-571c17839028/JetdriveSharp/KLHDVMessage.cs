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
	public class KLHDVMessage
	{
		protected KLHDVMessage()
		{

		}

		public KLHDVMessage(MessageKey key, UInt16 host, UInt16 destination, byte[] value)
		{
			if (value is null)
			{
				throw new ArgumentNullException(nameof(value));
			}

			this.Key = key;
			this.Host = host;
			this.Destination = destination;
			this.Value = value;
		}


		public MessageKey Key
		{
			get; protected set;
		}	

		public int Length
		{
			get
			{
				return this.Value.Length;
			}
		}

		public UInt16 Host
		{
			get; protected set;
		}

		public byte SequenceNumber
		{
			get;internal set;
		}

		public UInt16 Destination
		{
			get; protected set;
		}


		public byte[] Value
		{
			get; protected set;
		}
		

		public int CalcEncodedSize()
		{
			return sizeof(MessageKey) // KEY
				+ sizeof(UInt16) //LENGTH FIELD
				+ sizeof(UInt16) // HOST FIELD
				+ sizeof(byte)	//SEQUENCE FIELD
				+ sizeof(UInt16) // DESTINATION FIELD
				+ this.Length;	//Value length
		}

		public byte[] Encode()
		{
			byte[] data = new byte[CalcEncodedSize()];
			Encode(data, 0);
			return data;
		}


		public void Encode(byte[] dst, int dstOffset)
		{

			int idx = 0;

			//KEY
			dst[dstOffset + idx++] = (byte)this.Key;

			//LENGTH
			BitConverter.GetBytes(this.Length).CopyTo(dst, dstOffset + idx);
			idx += sizeof(UInt16);

			//HOST
			BitConverter.GetBytes(this.Host).CopyTo(dst, dstOffset + idx);
			idx += sizeof(UInt16);

			//SEQ NUM
			dst[dstOffset + idx++] = this.SequenceNumber;

			//DESTINATION HOST
			BitConverter.GetBytes(this.Destination).CopyTo(dst, dstOffset + idx);
			idx += sizeof(UInt16);

			//Value data
			Buffer.BlockCopy(this.Value, 0, dst, dstOffset + idx, this.Value.Length);

		}


	}
}
