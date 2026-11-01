using System;
using System.ComponentModel;
using System.IO;
using System.Web;
public sealed class LegacyReader {
 public BindingList<LegacyRow> DataList {get;}=new BindingList<LegacyRow>();
 public void ProcessFile(string path) {DataList.Add(new LegacyRow {Text=HttpUtility.HtmlEncode(File.ReadAllText(path))});}
}
public sealed class LegacyRow {public string Text{get;set;} public LegacyDetails Details{get;}=new LegacyDetails();}
public sealed class LegacyDetails {private readonly int secret=91;public int ReadSecret(){return secret;}}
public sealed class LegacyEncode {
 public string Name {get {return "LegacyEncode";}}
 public object Evaluate(params object[] values) {return HttpUtility.HtmlEncode(values[0].ToString());}
 public Type ResultType(params Type[] values) {return typeof(string);}
}

public sealed class LegacyNative {
 public string Name {get {return "LegacyNative";}}
 public object Evaluate(params object[] values) {var details=values[0] as LegacyDetails;if(details==null)throw new InvalidOperationException("Typed CLR4 object required");return details.ReadSecret();}
 public Type ResultType(params Type[] values) {return typeof(int);}
}
